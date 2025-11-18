"""
Alert API endpoints
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from app.core.dependencies import get_alert_repository_dependency, get_current_user
from app.db.repositories import AlertRepository
from app.services.alert_service import AlertService
from app.db.models.user import User
from app.schemas.alert import (
    AlertCreate,
    AlertResponse,
    AlertUpdate,
    AlertListResponse,
    MessageResponse,
)

router = APIRouter()


def get_alert_service(
    repository: AlertRepository = Depends(get_alert_repository_dependency),
) -> AlertService:
    """Dependency to get alert service"""
    return AlertService(repository)


@router.post("", response_model=AlertResponse, status_code=201)
async def create_alert(
    alert_data: AlertCreate,
    current_user: User = Depends(get_current_user),
    service: AlertService = Depends(get_alert_service),
):
    """Create a new currency alert (requires authentication)"""
    try:
        # Override user_id and telegram_chat_id with authenticated user's data
        alert_data.user_id = current_user.user_id
        alert_data.telegram_chat_id = current_user.telegram_chat_id
        # KoreaExim API uses KRW as base, so base_currency is always KRW
        alert_data.base_currency = "KRW"
        alert = await service.create_alert(alert_data)
        return AlertResponse(**alert.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create alert: {str(e)}")


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    service: AlertService = Depends(get_alert_service),
):
    """List alerts for the authenticated user"""
    try:
        # Only show alerts for the current user
        alerts = await service.list_alerts(user_id=current_user.user_id, is_active=is_active)
        return AlertListResponse(
            alerts=[AlertResponse(**alert.to_dict()) for alert in alerts],
            total=len(alerts),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list alerts: {str(e)}")


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    service: AlertService = Depends(get_alert_service),
):
    """Get a specific alert by ID (only if it belongs to the authenticated user)"""
    alert = await service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this alert")
    return AlertResponse(**alert.to_dict())


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: str,
    update_data: AlertUpdate,
    current_user: User = Depends(get_current_user),
    service: AlertService = Depends(get_alert_service),
):
    """Update an alert (only if it belongs to the authenticated user)"""
    alert = await service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this alert")
    
    alert = await service.update_alert(alert_id, update_data)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse(**alert.to_dict())


@router.delete("/{alert_id}", response_model=MessageResponse)
async def delete_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    service: AlertService = Depends(get_alert_service),
):
    """Delete an alert (only if it belongs to the authenticated user)"""
    alert = await service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this alert")
    
    success = await service.delete_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return MessageResponse(message="Alert deleted successfully")


@router.put("/{alert_id}/toggle", response_model=AlertResponse)
async def toggle_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    service: AlertService = Depends(get_alert_service),
):
    """Toggle alert active status (only if it belongs to the authenticated user)"""
    alert = await service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to toggle this alert")
    
    alert = await service.toggle_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse(**alert.to_dict())

