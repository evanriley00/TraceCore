from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterResponse(TokenResponse):
    api_key: str
    user: UserRead


class LoginResponse(TokenResponse):
    user: UserRead

