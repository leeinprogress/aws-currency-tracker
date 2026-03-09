from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Any, Dict, List, Optional
import json

import boto3
from boto3.dynamodb.conditions import Key

from app.core.config import settings
from app.domain.repositories import INotificationHistoryRepository
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

_TTL_DAYS = 90


def _to_dynamodb_safe(obj: Any) -> Any:
    """Recursively convert floats to Decimal for DynamoDB storage."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_dynamodb_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_dynamodb_safe(v) for v in obj]
    return obj


def _from_dynamodb_safe(obj: Any) -> Any:
    """Recursively convert Decimal back to float from DynamoDB items."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _from_dynamodb_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_dynamodb_safe(v) for v in obj]
    return obj


class DynamoDBNotificationHistoryRepository(INotificationHistoryRepository):
    """
    Schema
    ------
    PK  : user_id (String)
    SK  : sk = triggered_at#alert_id  (String, most-recent-first order preserved)
    GSI : currency-index (PK=currency)
    TTL : ttl (90 days)
    """

    def __init__(self, table_name: Optional[str] = None) -> None:
        resource = boto3.resource("dynamodb")
        self.table = resource.Table(
            table_name or settings.NOTIFICATION_HISTORY_TABLE_NAME
        )

    async def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        triggered_at = record.get("triggered_at", datetime.now(UTC).isoformat())
        alert_id = record.get("alert_id", "")
        sk = f"{triggered_at}#{alert_id}"

        now = datetime.now(UTC)
        ttl = int((now + timedelta(days=_TTL_DAYS)).timestamp())

        item: Dict[str, Any] = {
            "user_id": record["user_id"],
            "sk": sk,
            "triggered_at": triggered_at,
            "alert_id": alert_id,
            "currency": record.get("currency", ""),
            "channel": record.get("channel", "telegram"),
            "ttl": ttl,
        }

        if "target_rate" in record:
            item["target_rate"] = Decimal(str(record["target_rate"]))
        if "actual_rate" in record:
            item["actual_rate"] = Decimal(str(record["actual_rate"]))
        if "direction" in record:
            item["direction"] = record["direction"]

        self.table.put_item(Item=item)
        logger.info("notification_history_saved", user_id=record["user_id"], sk=sk)
        return {**record, "sk": sk}

    async def find_by_user(
        self,
        user_id: str,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        query_kwargs: Dict[str, Any] = {
            "KeyConditionExpression": Key("user_id").eq(user_id),
            "Limit": limit,
            "ScanIndexForward": False,  # newest first
        }
        if cursor:
            try:
                exclusive_start_key = json.loads(cursor)
                query_kwargs["ExclusiveStartKey"] = exclusive_start_key
            except (json.JSONDecodeError, TypeError):
                pass

        response = self.table.query(**query_kwargs)
        items = [_from_dynamodb_safe(item) for item in response.get("Items", [])]

        next_cursor: Optional[str] = None
        if "LastEvaluatedKey" in response:
            next_cursor = json.dumps(response["LastEvaluatedKey"])

        return items, next_cursor


__all__ = ["DynamoDBNotificationHistoryRepository"]
