from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import decode_access_token, hash_api_key
from app.db.models import User
from app.services.cache import DecisionCache, RateLimiter

bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Generator[Session, None, None]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_cache(request: Request) -> DecisionCache:
    return request.app.state.cache


def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


def get_current_user(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_scheme),
) -> User:
    user: User | None = None

    if credentials is not None:
        try:
            payload = decode_access_token(credentials.credentials, settings)
            subject = payload.get("sub")
            if subject is None:
                raise ValueError("Token missing subject")
            user = db.get(User, int(subject))
        except Exception as exc:  # pragma: no cover
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
            ) from exc
    elif api_key is not None:
        user = db.scalar(select(User).where(User.api_key_hash == hash_api_key(api_key)))

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return user

