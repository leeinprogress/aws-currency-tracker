from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.domain.entities.user import User
from app.domain.notification import NotificationService
from app.domain.repositories import IUserRepository
from app.infrastructure.notifications.telegram import TelegramNotificationService
from app.infrastructure.persistence.repositories import get_user_repository
from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_notification_service() -> NotificationService:
    return TelegramNotificationService(token=settings.TELEGRAM_BOT_TOKEN)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repository: IUserRepository = Depends(get_user_repository),
) -> User:
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
    
    user = await user_repository.find_by_id(user_id)
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user
