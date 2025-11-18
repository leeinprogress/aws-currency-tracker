"""
Repository factories
"""
from functools import lru_cache

from app.db.repositories.alert_repository import AlertRepository, DynamoDBAlertRepository
from app.db.repositories.user_repository import UserRepository, DynamoDBUserRepository


@lru_cache
def get_alert_repository() -> AlertRepository:
    """Return singleton alert repository"""
    return DynamoDBAlertRepository()


@lru_cache
def get_user_repository() -> UserRepository:
    """Return singleton user repository"""
    return DynamoDBUserRepository()


__all__ = [
    "AlertRepository",
    "UserRepository",
    "get_alert_repository",
    "get_user_repository",
]

