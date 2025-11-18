"""
User domain model
"""
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class User:
    """User domain model"""
    user_id: str
    email: str
    telegram_chat_id: str
    hashed_password: str
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self, exclude_password: bool = True) -> dict:
        """Convert to dictionary"""
        result = {
            "user_id": self.user_id,
            "email": self.email,
            "telegram_chat_id": self.telegram_chat_id,
            "is_active": self.is_active,
        }
        if not exclude_password:
            result["hashed_password"] = self.hashed_password
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            result["updated_at"] = self.updated_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Create from dictionary"""
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
            user_id=data["user_id"],
            email=data["email"],
            telegram_chat_id=data["telegram_chat_id"],
            hashed_password=data.get("hashed_password", ""),
            is_active=bool(data.get("is_active", True)),
            created_at=created_at,
            updated_at=updated_at,
        )

