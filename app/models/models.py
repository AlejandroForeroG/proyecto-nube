import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

UTC = timezone.utc


class VideoStatus(enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    done = "done"
    failed = "failed"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    first_name = Column(String(255))
    last_name = Column(String(255), nullable=False)
    city = Column(String(255), nullable=False)
    country = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    videos = relationship("Video", back_populates="user", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="user", cascade="all, delete-orphan")


class Video(Base):
    __tablename__ = "videos"
    id = Column(Integer, primary_key=True)
    video_id = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    status = Column(String(32), default="uploaded")
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    original_path = Column(String(500))
    processed_path = Column(String(500))
    task_id = Column(String(128))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_public = Column(Boolean, default=False)

    user = relationship("User", back_populates="videos")
    votes = relationship("Vote", back_populates="video", cascade="all, delete-orphan")


class Vote(Base):
    __tablename__ = "votes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now(UTC))

    user = relationship("User", back_populates="votes")
    video = relationship("Video", back_populates="votes")


class test(Base):
    __tablename__ = "test"
    id = Column(Integer, primary_key=True)
