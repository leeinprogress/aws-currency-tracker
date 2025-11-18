"""
FastAPI dependencies
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.db.repositories import (
    AlertRepository,
    UserRepository,
    get_alert_repository,
    get_user_repository,
)
from app.core.security import decode_access_token
from app.db.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_alert_repository_dependency() -> AlertRepository:
    """FastAPI dependency for alert repository"""
    return get_alert_repository()


def get_user_repository_dependency() -> UserRepository:
    """FastAPI dependency for user repository"""
    return get_user_repository()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repository: UserRepository = Depends(get_user_repository_dependency),
) -> User:
    """Dependency to get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = await user_repository.get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user
