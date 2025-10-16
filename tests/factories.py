from __future__ import annotations

from dataclasses import dataclass

from faker import Faker

from app.core.security import hash_password
from app.models import User, Video, VideoStatus, Vote

fake = Faker()


@dataclass
class UserFactory:
    db_session: any

    def create(self, **overrides) -> User:
        password = overrides.pop("password", fake.password(length=12))
        user = User(
            email=overrides.get("email", fake.unique.email()),
            first_name=overrides.get("first_name", fake.first_name()),
            last_name=overrides.get("last_name", fake.last_name()),
            city=overrides.get("city", fake.city()),
            country=overrides.get("country", fake.country()),
            hashed_password=hash_password(password),
            is_active=overrides.get("is_active", True),
        )
        self.db_session.add(user)
        self.db_session.commit()
        self.db_session.refresh(user)

        setattr(user, "_plain_password", password)
        return user


@dataclass
class VideoFactory:
    db_session: any

    def create(self, **overrides) -> Video:
        user: User | None = overrides.pop("user", None)
        if user is None:
            user = UserFactory(self.db_session).create()

        video = Video(
            video_id=overrides.get("video_id", fake.uuid4().replace("-", "")[:12]),
            title=overrides.get("title", fake.sentence(nb_words=3)),
            status=overrides.get("status", VideoStatus.done.value),
            original_path=overrides.get("original_path", "uploads/fake.mp4"),
            processed_path=overrides.get("processed_path", None),
            task_id=overrides.get("task_id", fake.uuid4()),
            user_id=user.id,
            is_public=overrides.get("is_public", False),
        )
        self.db_session.add(video)
        self.db_session.commit()
        self.db_session.refresh(video)
        return video


@dataclass
class VoteFactory:
    db_session: any

    def create(self, **overrides) -> Vote:
        user: User | None = overrides.pop("user", None)
        video: Video | None = overrides.pop("video", None)
        if user is None:
            user = UserFactory(self.db_session).create()
        if video is None:
            video = VideoFactory(self.db_session).create(user=user)
        vote = Vote(user_id=user.id, video_id=video.id)
        self.db_session.add(vote)
        self.db_session.commit()
        self.db_session.refresh(vote)
        return vote


def make_factories(db_session) -> tuple[UserFactory, VideoFactory, VoteFactory]:
    return (UserFactory(db_session), VideoFactory(db_session), VoteFactory(db_session))
