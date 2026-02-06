import uuid
from typing import List, Optional

from app.domain.entities.alert import Alert
from app.domain.repositories import IAlertRepository
from app.schemas.alert import AlertCreate, AlertUpdate
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

MAX_ALERTS_PER_USER = 15


class AlertService:
    def __init__(self, repository: IAlertRepository):
        self.repository = repository
    
    async def create_alert(self, alert_data: AlertCreate) -> Alert:
        if not alert_data.user_id or not alert_data.telegram_chat_id:
            logger.error("alert_creation_failed", reason="missing_required_fields")
            raise ValueError("user_id and telegram_chat_id are required")
        
        existing_alerts = await self.repository.find_by_user(alert_data.user_id)
        if len(existing_alerts) >= MAX_ALERTS_PER_USER:
            logger.warning("alert_limit_reached", user_id=alert_data.user_id, count=len(existing_alerts))
            raise ValueError(f"Maximum {MAX_ALERTS_PER_USER} alerts allowed per user")

        logger.info(
            "creating_alert",
            user_id=alert_data.user_id,
            target_currency=alert_data.target_currency,
            target_rate=alert_data.target_rate,
            condition=alert_data.condition,
        )

        alert = Alert(
            alert_id=str(uuid.uuid4()),
            user_id=alert_data.user_id,
            telegram_chat_id=alert_data.telegram_chat_id,
            target_currency=alert_data.target_currency,
            target_rate=alert_data.target_rate,
            condition=alert_data.condition,
            rate_type=alert_data.rate_type,
            is_active=True,
            idempotency_key=getattr(alert_data, "idempotency_key", None),
        )
        created_alert = await self.repository.save(alert)
        
        logger.info("alert_created", alert_id=created_alert.alert_id)
        return created_alert
    
    async def get_alert(self, alert_id: str) -> Optional[Alert]:
        return await self.repository.find_by_id(alert_id)
    
    async def list_alerts(self, user_id: Optional[str] = None, is_active: Optional[bool] = None) -> List[Alert]:
        if user_id:
            return await self.repository.find_by_user(user_id=user_id, is_active=is_active)
        return []
    
    async def update_alert(self, alert_id: str, update_data: AlertUpdate) -> Optional[Alert]:
        alert = await self.repository.find_by_id(alert_id)
        if not alert:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        return await self.repository.update(alert_id, **update_dict)
    
    async def delete_alert(self, alert_id: str) -> bool:
        logger.info("deleting_alert", alert_id=alert_id)
        result = await self.repository.delete(alert_id)
        
        if result:
            logger.info("alert_deleted", alert_id=alert_id)
        else:
            logger.warning("alert_deletion_failed", alert_id=alert_id, reason="not_found")
        
        return result
    
    async def toggle_alert(self, alert_id: str) -> Optional[Alert]:
        alert = await self.repository.find_by_id(alert_id)
        if not alert:
            logger.warning("toggle_alert_failed", alert_id=alert_id, reason="not_found")
            return None
        
        alert.is_active = not alert.is_active
        new_status = alert.is_active
        
        logger.info(
            "toggling_alert",
            alert_id=alert_id,
            new_status="active" if new_status else "inactive"
        )
        
        return await self.repository.update(alert_id, is_active=new_status)
