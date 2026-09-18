from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


Role = Literal["user", "admin"]


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    role: Role
    plan: str
    monthly_token_quota: int
    created_at: datetime
    last_login_at: datetime | None = None
    is_active: bool


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user: UserPublic
    access_token: str


class UserInDB(BaseModel):
    id: str
    email: EmailStr
    role: Role
    plan: str
    monthly_token_quota: int
    created_at: datetime
    last_login_at: datetime | None = None
    is_active: bool
