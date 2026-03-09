from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=8)
    telegram_chat_id: Optional[str] = Field(None)


class UserLogin(BaseModel):
    email: EmailStr = Field(...)
    password: str = Field(...)


class UserProfileUpdate(BaseModel):
    telegram_chat_id: Optional[str] = Field(None)


class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    auth_provider: str = "local"
    telegram_chat_id: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(BaseModel):
    """Extended profile returned by GET /users/me."""

    user_id: str
    email: EmailStr
    auth_provider: str = "local"
    telegram_chat_id: Optional[str] = None
    created_at: Optional[datetime] = None
    alert_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
