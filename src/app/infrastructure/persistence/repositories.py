from functools import lru_cache

from app.domain.repositories import (
    IAlertRepository,
    INotificationHistoryRepository,
    IRateHistoryRepository,
    IUserRepository,
)
from app.infrastructure.persistence.dynamodb_alert_repository import DynamoDBAlertRepository
from app.infrastructure.persistence.dynamodb_notification_history_repository import (
    DynamoDBNotificationHistoryRepository,
)
from app.infrastructure.persistence.dynamodb_rate_history_repository import DynamoDBRateHistoryRepository
from app.infrastructure.persistence.dynamodb_user_repository import DynamoDBUserRepository


@lru_cache
def get_alert_repository() -> IAlertRepository:
    return DynamoDBAlertRepository()


@lru_cache
def get_user_repository() -> IUserRepository:
    return DynamoDBUserRepository()


@lru_cache
def get_rate_history_repository() -> IRateHistoryRepository:
    return DynamoDBRateHistoryRepository()


@lru_cache
def get_notification_history_repository() -> INotificationHistoryRepository:
    return DynamoDBNotificationHistoryRepository()


__all__ = [
    "get_alert_repository",
    "get_notification_history_repository",
    "get_rate_history_repository",
    "get_user_repository",
]
