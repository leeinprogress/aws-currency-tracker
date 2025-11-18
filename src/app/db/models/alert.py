"""
Alert data models (database-agnostic)
"""
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Alert:
    """Alert domain model"""
    alert_id: str
    user_id: str
    telegram_chat_id: str
    base_currency: str  # KoreaExim API uses KRW as base, so always "KRW"
    target_currency: str  # e.g., USD, EUR
    target_rate: float
    condition: str  # "above" or "below"
    rate_type: str  # "TTS", "TTB", or "DEAL_BAS_R"
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary, converting float to Decimal for DynamoDB."""
        result = {
            "alert_id": self.alert_id,
            "user_id": self.user_id,
            "telegram_chat_id": self.telegram_chat_id,
            "base_currency": self.base_currency,
            "target_currency": self.target_currency,
            "target_rate": Decimal(str(self.target_rate)),
            "condition": self.condition,
            "rate_type": self.rate_type,
            "is_active": self.is_active,
        }
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            result["updated_at"] = self.updated_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "Alert":
        """Create from dictionary"""
        # Handle datetime strings
        created_at = None
        updated_at = None
        if "created_at" in data:
            if isinstance(data["created_at"], str):
                created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            elif isinstance(data["created_at"], datetime):
                created_at = data["created_at"]
        if "updated_at" in data:
            if isinstance(data["updated_at"], str):
                updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
            elif isinstance(data["updated_at"], datetime):
                updated_at = data["updated_at"]
        
        return cls(
            alert_id=data["alert_id"],
            user_id=data["user_id"],
            telegram_chat_id=data["telegram_chat_id"],
            base_currency=data["base_currency"],
            target_currency=data["target_currency"],
            target_rate=float(data["target_rate"]),
            condition=data["condition"],
            rate_type=data.get("rate_type", "TTS"),  # Default: TTS
            is_active=bool(data.get("is_active", True)),
            created_at=created_at,
            updated_at=updated_at,
        )

