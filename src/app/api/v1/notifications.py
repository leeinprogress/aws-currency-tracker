from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_current_user
from app.domain.entities.user import User
from app.domain.repositories import INotificationHistoryRepository
from app.infrastructure.persistence.repositories import get_notification_history_repository
from app.schemas.notification import NotificationHistoryResponse

router = APIRouter()


@router.get("", response_model=NotificationHistoryResponse)
async def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    repo: INotificationHistoryRepository = Depends(get_notification_history_repository),
):
    """Return paginated notification history for the current user, newest first."""
    try:
        items, next_cursor = await repo.find_by_user(
            user_id=current_user.user_id,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch notifications: {exc}")

    return NotificationHistoryResponse(
        items=items,
        total=len(items),
        next_cursor=next_cursor,
    )
