from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.schemas.auth import LoginResponse, RegisterResponse, UserCreate, UserLogin


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def register_user(self, db: Session, payload: UserCreate) -> RegisterResponse:
        existing_user = db.scalar(select(User).where(User.email == payload.email))
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with that email already exists",
            )

        api_key = generate_api_key()
        user = User(
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            api_key_hash=hash_api_key(api_key),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        return RegisterResponse(
            access_token=create_access_token(str(user.id), self.settings),
            api_key=api_key,
            user=user,
        )

    def login_user(self, db: Session, payload: UserLogin) -> LoginResponse:
        user = db.scalar(select(User).where(User.email == payload.email))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        return LoginResponse(
            access_token=create_access_token(str(user.id), self.settings),
            user=user,
        )

