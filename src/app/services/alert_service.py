"""
Alert service layer - business logic
"""
import uuid
from typing import List, Optional

from app.db.repositories import AlertRepository
from app.db.models.alert import Alert
from app.schemas.alert import AlertCreate, AlertUpdate


class AlertService:
    """Alert business logic service"""

    def __init__(self, repository: AlertRepository):
        self.repository = repository
    
    async def create_alert(self, alert_data: AlertCreate) -> Alert:
        """Create a new alert"""
        if not alert_data.user_id or not alert_data.telegram_chat_id:
            raise ValueError("user_id and telegram_chat_id are required to create an alert")

        alert = Alert(
            alert_id=str(uuid.uuid4()),
            user_id=alert_data.user_id,
            telegram_chat_id=alert_data.telegram_chat_id,
            base_currency=alert_data.base_currency,
            target_currency=alert_data.target_currency,
            target_rate=alert_data.target_rate,
            condition=alert_data.condition,
            rate_type=alert_data.rate_type,
            is_active=True,
        )
        return await self.repository.create_alert(alert)
    
    async def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get an alert by ID"""
        return await self.repository.get_alert(alert_id)
    
    async def list_alerts(self, user_id: Optional[str] = None, is_active: Optional[bool] = None) -> List[Alert]:
        """List alerts with optional filters"""
        return await self.repository.list_alerts(user_id=user_id, is_active=is_active)
    
    async def update_alert(self, alert_id: str, update_data: AlertUpdate) -> Optional[Alert]:
        """Update an alert"""
        update_dict = update_data.model_dump(exclude_unset=True)
        return await self.repository.update_alert(alert_id, **update_dict)
    
    async def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert"""
        return await self.repository.delete_alert(alert_id)
    
    async def toggle_alert(self, alert_id: str) -> Optional[Alert]:
        """Toggle alert active status"""
        alert = await self.repository.get_alert(alert_id)
        if not alert:
            return None
        return await self.repository.update_alert(alert_id, is_active=not alert.is_active)

