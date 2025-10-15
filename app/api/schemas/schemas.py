from datetime import datetime

from pydantic import BaseModel, EmailStr

class ErrorMessage(BaseModel):
    detail: str
    status_code: int


class UserCreate(BaseModel):
    email: EmailStr
    password1: str
    password2: str
    first_name: str
    last_name: str
    city: str
    country: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginJSON(BaseModel):
    email: EmailStr
    password: str


class Vote(BaseModel):
    id: int
    user_id: int
    video_id: int
    created_at: datetime


