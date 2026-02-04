from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    user_id: str
    email: str
    is_active: bool
    auth_provider: str = "local"           # "local" | "google"
    telegram_chat_id: Optional[str] = None
    hashed_password: Optional[str] = None  # None for Google-only users
    google_id: Optional[str] = None        # sparse — only for Google users
    refresh_token_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def deactivate(self) -> None:
        self.is_active = False

    def activate(self) -> None:
        self.is_active = True
