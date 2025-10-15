from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Video(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    video_id: str
    title: str
    status: str
    original_path: str
    processed_path: Optional[str] = None
    task_id: Optional[str] = None
    user_id: int
    is_public: bool
    uploaded_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UploadVideoResponse(BaseModel):
    message: str
    task_id: str


class UserVideoResponse(BaseModel):
    video_id: str
    title: str
    status: str
    uploaded_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    processed_url: Optional[str] = None


class VideoDetailResponse(BaseModel):
    video_id: str
    title: str
    status: str
    uploaded_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    original_url: Optional[str] = None
    processed_url: Optional[str] = None
    votes: int


class DeleteVideoResponse(BaseModel):
    message: str
    video_id: str
