from datetime import datetime, timedelta, UTC
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Depends, Query

from app.core.dependencies import get_current_user
from app.domain.entities.user import User
from app.domain.entities.alert import Alert
from app.domain.repositories import IAlertRepository
from app.infrastructure.persistence.repositories import get_alert_repository
from app.services.alert_service import AlertService
from app.schemas.alert import (
    AlertCreate,
    AlertResponse,
    AlertUpdate,
    AlertListResponse,
    MessageResponse,
)

_IDEMPOTENCY_TTL_MINUTES = 5

router = APIRouter()


def alert_to_response(alert: Alert) -> AlertResponse:
    return AlertResponse(
        alert_id=alert.alert_id,
        user_id=alert.user_id,
        telegram_chat_id=alert.telegram_chat_id,
        target_currency=alert.target_currency,
        target_rate=alert.target_rate,
        condition=alert.condition,
        rate_type=alert.rate_type,
        is_active=alert.is_active,
        idempotency_key=alert.idempotency_key,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


def get_alert_service(
    repository: IAlertRepository = Depends(get_alert_repository),
) -> AlertService:
    return AlertService(repository)


@router.post("", response_model=AlertResponse, status_code=201)
async def create_alert(
    alert_data: AlertCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    service: AlertService = Depends(get_alert_service),
):
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header is required",
        )

    # Check for a recent alert created with this idempotency key
    existing_alerts = await service.list_alerts(user_id=current_user.user_id)
    ttl_cutoff = datetime.now(UTC) - timedelta(minutes=_IDEMPOTENCY_TTL_MINUTES)
    for alert in existing_alerts:
        if (
            getattr(alert, "idempotency_key", None) == idempotency_key
            and alert.created_at
            and alert.created_at.replace(tzinfo=UTC) >= ttl_cutoff
        ):
            return alert_to_response(alert)

    try:
        alert_data.user_id = current_user.user_id
        alert_data.telegram_chat_id = current_user.telegram_chat_id
        alert_data.idempotency_key = idempotency_key
        alert = await service.create_alert(alert_data)
        return alert_to_response(alert)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create alert: {str(e)}")


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    service: AlertService = Depends(get_alert_service),
):
    try:
        alerts = await service.list_alerts(user_id=current_user.user_id, is_active=is_active)
        return AlertListResponse(
            alerts=[alert_to_response(alert) for alert in alerts],
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
    alert = await service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this alert")
    return alert_to_response(alert)


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: str,
    update_data: AlertUpdate,
    current_user: User = Depends(get_current_user),
    service: AlertService = Depends(get_alert_service),
):
    alert = await service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this alert")
    
    alert = await service.update_alert(alert_id, update_data)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert_to_response(alert)


@router.delete("/{alert_id}", response_model=MessageResponse)
async def delete_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    service: AlertService = Depends(get_alert_service),
):
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
    alert = await service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to toggle this alert")
    
    alert = await service.toggle_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert_to_response(alert)
