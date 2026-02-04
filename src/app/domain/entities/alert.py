from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Alert:
    alert_id: str
    user_id: str
    telegram_chat_id: str
    target_currency: str
    target_rate: float
    condition: str  # "above" | "below"
    rate_type: str  # "TTS" | "TTB" | "DEAL_BAS_R"
    is_active: bool
    idempotency_key: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def should_trigger(self, current_rate: float) -> bool:
        if not self.is_active:
            return False
        
        if self.condition == "above":
            return current_rate >= self.target_rate
        elif self.condition == "below":
            return current_rate <= self.target_rate
        
        return False
    
    def deactivate(self) -> None:
        self.is_active = False
    
    def activate(self) -> None:
        self.is_active = True
    
    def update_target_rate(self, new_rate: float) -> None:
        if new_rate <= 0:
            raise ValueError("Target rate must be positive")
        self.target_rate = new_rate
