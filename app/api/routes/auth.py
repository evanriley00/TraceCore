from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_settings
from app.db.models import User
from app.schemas.auth import LoginResponse, RegisterResponse, UserCreate, UserLogin, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db), settings=Depends(get_settings)):
    return AuthService(settings).register_user(db, payload)


@router.post("/login", response_model=LoginResponse)
def login(payload: UserLogin, db: Session = Depends(get_db), settings=Depends(get_settings)):
    return AuthService(settings).login_user(db, payload)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user

