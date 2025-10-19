import uuid
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.responses.video_responses import (
    delete_video_responses,
    upload_video_responses,
    user_videos_responses,
    video_detail_responses,
)
from app.api.schemas.videos import (
    DeleteVideoResponse,
    UploadVideoResponse,
    UserVideoResponse,
    VideoDetailResponse,
)
from app.celery_worker import process_video_task
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.storage import LocalStorage
from app.models import User, Video, VideoStatus, Vote
from app.models.models import UTC


def auth_and_set_user(request: Request, user: User = Depends(get_current_user)):
    request.state.user = user


def get_processed_videos_url(request: Request):
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    forwarded_host = request.headers.get("x-forwarded-host")
    host = forwarded_host or request.headers.get("host", request.url.netloc)
    processed_route = settings.PROCESSED_DIR
    return f"{scheme}://{host}/{processed_route}/"


router = APIRouter(dependencies=[Depends(auth_and_set_user)])
CHUNK_SIZE = 1024 * 1024
ALLOWED_EXTS = {".mp4", ".mov", ".mkv", ".webm"}


@router.post(
    "/upload",
    status_code=HTTPStatus.CREATED,
    responses=upload_video_responses,
    response_model=UploadVideoResponse,
)
async def upload_video(
    request: Request,
    video_file: UploadFile = File(...),
    title: str = Form(...),
    db: Session = Depends(get_db),
):
    if not video_file.content_type or not video_file.content_type.startswith("video/"):
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "Tipo de archivo invalido, debe ser un video"
        )

    video_uuid = str(uuid.uuid4())
    ext = (Path(video_file.filename).suffix or ".mp4").lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, f"Tipo de archivo no soportado {ext}"
        )

    original_rel = f"{video_uuid}_original{ext}"
    storage = LocalStorage(base_dir=settings.UPLOAD_PATH)
    try:
        saved_path = await storage.save_async(
            video_file,
            original_rel,
            chunk_size=CHUNK_SIZE,
            max_size=settings.MAX_FILE_SIZE,
        )
    except ValueError:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "El archivo excede el tamaño limite"
        )

    current_user = request.state.user
    v = Video(
        video_id=video_uuid,
        title=title,
        status="uploaded",
        original_path=saved_path,
        user_id=current_user.id,
        uploaded_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(v)
    db.commit()
    db.refresh(v)

    task = process_video_task.delay(v.id, saved_path)
    v.task_id = task.id
    db.commit()

    return {
        "message": "Video subido correctamente. Procesamiento en progeso.",
        "task_id": task.id,
        "video_id": v.video_id,
    }


@router.post(
    "/upload-mock",
    status_code=HTTPStatus.ACCEPTED,
    responses=upload_video_responses,
    response_model=UploadVideoResponse,
)
async def upload_video_mock(
    request: Request,
    video_file: UploadFile = File(...),
    title: str = Form(...),
    db: Session = Depends(get_db),
):
    if not video_file.content_type or not video_file.content_type.startswith("video/"):
        print(video_file.content_type)
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "Tipo de archivo invalido, debe ser un video"
        )

    video_uuid = str(uuid.uuid4())
    ext = (Path(video_file.filename).suffix or ".mp4").lower()
    if ext not in ALLOWED_EXTS:
        print(ext)
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, f"Tipo de archivo no soportado {ext}"
        )

    original_rel = f"{video_uuid}_original{ext}"
    storage = LocalStorage(base_dir=settings.UPLOAD_PATH)
    try:
        saved_path = await storage.save_async(
            video_file,
            original_rel,
            chunk_size=CHUNK_SIZE,
            max_size=settings.MAX_FILE_SIZE,
        )
    except ValueError as e:
        print(e)
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "El archivo excede el tamaño limite"
        )

    current_user = request.state.user
    v = Video(
        video_id=video_uuid,
        title=title,
        status="uploaded",
        original_path=saved_path,
        user_id=current_user.id,
        uploaded_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(v)
    db.commit()
    db.refresh(v)

    mock_task_id = f"mock-{video_uuid}"
    v.task_id = mock_task_id
    db.commit()

    return {
        "message": "Video subido correctamente (mock mode - sin procesamiento).",
        "task_id": mock_task_id,
        "video_id": v.video_id,
    }


@router.get("", responses=user_videos_responses, response_model=List[UserVideoResponse])
async def get_user_videos(
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = request.state.user
    videos = (
        db.query(Video)
        .filter(
            Video.user_id == current_user.id,
            Video.status == VideoStatus.done.value,
        )
        .all()
    )
    processed_base_url = get_processed_videos_url(request)
    response: List[UserVideoResponse] = []
    for v in videos:
        processed_url = None
        if v.processed_path:
            processed_url = f"{processed_base_url}{Path(v.processed_path).name}"

        response.append(
            UserVideoResponse(
                video_id=v.video_id,
                title=v.title,
                status=v.status,
                updated_at=v.updated_at,
                uploaded_at=v.uploaded_at,
                processed_url=processed_url,
            )
        )
    return response


@router.get(
    "/{video_id}",
    responses=video_detail_responses,
    response_model=VideoDetailResponse,
)
async def get_video_detail(
    video_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Video no encontrado")

    processed_base_url = get_processed_videos_url(request)

    original_url = None
    if video.original_path:
        original_url = f"{processed_base_url}/{Path(video.original_path).name}"

    processed_url = None
    processed_at = None
    if video.processed_path:
        processed_url = f"{processed_base_url}/{Path(video.processed_path).name}"
        processed_at = video.updated_at

    votes_count = (
        db.query(func.count(Vote.id)).filter(Vote.video_id == video.id).scalar() or 0
    )

    return VideoDetailResponse(
        video_id=video.video_id,
        title=video.title,
        status=video.status,
        uploaded_at=video.uploaded_at,
        processed_at=processed_at,
        original_url=original_url,
        processed_url=processed_url,
        votes=votes_count,
    )


@router.delete(
    "/{video_id}",
    responses=delete_video_responses,
    response_model=DeleteVideoResponse,
)
async def delete_video(
    video_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = request.state.user
    video = db.query(Video).filter(Video.video_id == video_id).first()
    if not video:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Video no encontrado")
    if video.user_id != current_user.id:
        raise HTTPException(
            HTTPStatus.FORBIDDEN, "No tiene permisos para eliminar este video"
        )
    if getattr(video, "is_public", False):
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            "El video ya está habilitado para votación y no puede eliminarse",
        )

    try:
        if video.original_path:
            Path(video.original_path).unlink(missing_ok=True)
    except Exception:
        pass
    try:
        if video.processed_path:
            Path(video.processed_path).unlink(missing_ok=True)
    except Exception:
        pass

    db.delete(video)
    db.commit()

    return DeleteVideoResponse(
        message="El video ha sido eliminado exitosamente.", video_id=video_id
    )
