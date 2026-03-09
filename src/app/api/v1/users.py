from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.core.exceptions import UserNotFoundError
from app.domain.entities.user import User
from app.domain.repositories import IAlertRepository, IUserRepository
from app.infrastructure.persistence.repositories import (
    get_alert_repository,
    get_user_repository,
)
from app.schemas.user import UserProfileResponse, UserProfileUpdate
from app.services.user_service import UserService

router = APIRouter()


def _get_user_service(
    user_repository: IUserRepository = Depends(get_user_repository),
    alert_repository: IAlertRepository = Depends(get_alert_repository),
) -> UserService:
    return UserService(user_repository, alert_repository)


@router.get("/me", response_model=UserProfileResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_user_service),
):
    alert_count = await service.count_alerts(current_user.user_id)
    return UserProfileResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        auth_provider=current_user.auth_provider,
        telegram_chat_id=current_user.telegram_chat_id,
        created_at=current_user.created_at,
        alert_count=alert_count,
    )


@router.put("/me", response_model=UserProfileResponse)
async def update_me(
    body: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_user_service),
):
    try:
        updated = await service.update_user(
            current_user.user_id,
            telegram_chat_id=body.telegram_chat_id,
        )
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    alert_count = await service.count_alerts(updated.user_id)
    return UserProfileResponse(
        user_id=updated.user_id,
        email=updated.email,
        auth_provider=updated.auth_provider,
        telegram_chat_id=updated.telegram_chat_id,
        created_at=updated.created_at,
        alert_count=alert_count,
    )


@router.delete("/me", status_code=204)
async def delete_me(
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_user_service),
):
    try:
        await service.delete_user(current_user.user_id)
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
