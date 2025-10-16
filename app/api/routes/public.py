from http import HTTPStatus
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.api.responses.video_responses import (
    public_videos_responses,
    rankings_responses,
    vote_video_responses,
)
from app.api.routes.videos import get_processed_videos_url
from app.api.schemas.videos import (
    PublicVideoResponse,
    RankingItem,
    VoteMessageResponse,
)
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User, Video, VideoStatus, Vote

router = APIRouter()


@router.get(
    "/videos",
    responses=public_videos_responses,
    response_model=List[PublicVideoResponse],
)
def list_public_videos(request: Request, db: Session = Depends(get_db)):
    processed_base_url = get_processed_videos_url(request)
    q = (
        db.query(Video, func.count(Vote.id).label("votes"))
        .outerjoin(Vote, Vote.video_id == Video.id)
        .filter(and_(Video.is_public, Video.status == VideoStatus.done.value))
        .group_by(Video.id)
        .order_by(Video.updated_at.desc())
    )
    items: List[PublicVideoResponse] = []
    for v, votes in q:
        processed_url = None
        if v.processed_path:
            processed_url = f"{processed_base_url}{v.processed_path.split('/')[-1]}"
        items.append(
            PublicVideoResponse(
                video_id=v.video_id,
                title=v.title,
                processed_url=processed_url,
                votes=int(votes or 0),
            )
        )
    return items


@router.post(
    "/videos/{video_id}/vote",
    responses=vote_video_responses,
    response_model=VoteMessageResponse,
)
def vote_public_video(
    video_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = (
        db.query(Video)
        .filter(
            and_(
                Video.video_id == video_id,
                Video.is_public,
                Video.status == VideoStatus.done.value,
            )
        )
        .first()
    )
    if not video:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Video no encontrado.")

    already = (
        db.query(Vote)
        .filter(and_(Vote.user_id == user.id, Vote.video_id == video.id))
        .first()
    )
    if already:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Ya has votado por este video.")

    v = Vote(user_id=user.id, video_id=video.id)
    db.add(v)
    db.commit()
    return VoteMessageResponse(message="Voto registrado exitosamente.")


@router.get("/rankings", responses=rankings_responses, response_model=List[RankingItem])
def get_rankings(
    db: Session = Depends(get_db),
    city: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    offset = (page - 1) * page_size
    base = (
        db.query(
            User.id,
            User.first_name,
            User.last_name,
            User.city,
            func.count(Vote.id).label("votes"),
        )
        .join(Video, Video.user_id == User.id)
        .outerjoin(Vote, Vote.video_id == Video.id)
        .filter(Video.is_public)
        .group_by(User.id, User.first_name, User.last_name, User.city)
        .order_by(func.count(Vote.id).desc(), User.id.asc())
    )
    if city:
        base = base.filter(User.city == city)

    rows = base.offset(offset).limit(page_size).all()
    items: List[RankingItem] = []
    for idx, (uid, first_name, last_name, ucity, votes) in enumerate(rows):
        username = (first_name or "").strip()
        if last_name:
            username = f"{username} {last_name}".strip()
        if not username:
            username = f"user-{uid}"
        items.append(
            RankingItem(
                position=offset + idx + 1,
                username=username,
                city=ucity,
                votes=int(votes or 0),
            )
        )
    return items

