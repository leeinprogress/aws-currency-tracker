from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.domain.entities.alert import Alert
from app.domain.entities.user import User
from app.domain.entities.rate_history import RateHistory


class IAlertRepository(ABC):
    @abstractmethod
    async def save(self, alert: Alert) -> Alert:
        pass
    
    @abstractmethod
    async def find_by_id(self, alert_id: str) -> Optional[Alert]:
        pass
    
    @abstractmethod
    async def find_by_user(self, user_id: str, is_active: Optional[bool] = None) -> List[Alert]:
        pass
    
    @abstractmethod
    async def find_all_active(self) -> List[Alert]:
        pass
    
    @abstractmethod
    async def delete(self, alert_id: str) -> bool:
        pass
    
    @abstractmethod
    async def update(self, alert_id: str, **kwargs) -> Optional["Alert"]:
        pass


class IUserRepository(ABC):
    @abstractmethod
    async def save(self, user: User) -> User:
        pass

    @abstractmethod
    async def find_by_id(self, user_id: str) -> Optional[User]:
        pass

    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    async def find_by_google_id(self, google_id: str) -> Optional[User]:
        pass

    @abstractmethod
    async def update(self, user_id: str, **kwargs: Any) -> Optional[User]:
        pass

    @abstractmethod
    async def delete(self, user_id: str) -> bool:
        pass


class IRateHistoryRepository(ABC):
    @abstractmethod
    async def save(self, rate_history: RateHistory) -> RateHistory:
        pass

    @abstractmethod
    async def save_batch(self, rates: List[RateHistory]) -> int:
        pass

    @abstractmethod
    async def find_by_currency_range(
        self,
        currency_code: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100,
    ) -> List[RateHistory]:
        pass

    @abstractmethod
    async def find_latest(self, currency_code: str) -> Optional[RateHistory]:
        pass


class INotificationHistoryRepository(ABC):
    @abstractmethod
    async def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def find_by_user(
        self,
        user_id: str,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        pass
