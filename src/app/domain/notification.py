from abc import ABC, abstractmethod
from typing import Any


class NotificationService(ABC):
    @abstractmethod
    async def send(self, user_id: str, message: str, metadata: dict[str, Any]) -> bool: ...
