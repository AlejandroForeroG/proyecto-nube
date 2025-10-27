from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.schemas.schemas import Token, UserCreate
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User

router = APIRouter()


@router.post("/signup", status_code=201)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(HTTPStatus.BAD_REQUEST, "El email ya esta registrado")
    if payload.password1 != payload.password2:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Las contraseñas no coinciden")
    u = User(
        email=payload.email,
        hashed_password=hash_password(payload.password1),
        first_name=payload.first_name,
        last_name=payload.last_name,
        city=payload.city,
        country=payload.country,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"id": u.id, "email": u.email}


@router.post("/login", response_model=Token)
async def login(request: Request, db: Session = Depends(get_db)):
    email = None
    password = None
    ct = request.headers.get("content-type", "")
    if ct.startswith("application/json"):
        body = await request.json()
        email = body.get("email")
        password = body.get("password")
    else:
        form = await request.form()
        email = form.get("username")
        password = form.get("password")
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Credenciales invalidas")
    token = create_access_token({"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_SECONDS,
    }
