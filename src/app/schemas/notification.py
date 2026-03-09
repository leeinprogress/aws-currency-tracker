from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class NotificationHistoryItem(BaseModel):
    user_id: str
    sk: str
    triggered_at: str
    alert_id: str
    currency: str
    channel: str
    target_rate: Optional[float] = None
    actual_rate: Optional[float] = None
    direction: Optional[str] = None


class NotificationHistoryResponse(BaseModel):
    items: List[Dict[str, Any]]
    total: int
    next_cursor: Optional[str] = None
