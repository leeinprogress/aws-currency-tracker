from datetime import datetime
from typing import List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from app.core.config import settings
from app.domain.entities.rate_history import RateHistory
from app.domain.repositories import IRateHistoryRepository
from app.infrastructure.persistence.mappers import RateHistoryMapper
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class DynamoDBRateHistoryRepository(IRateHistoryRepository):
    def __init__(self, table_name: Optional[str] = None):
        resource = boto3.resource("dynamodb")
        self.table = resource.Table(table_name or settings.RATE_HISTORY_TABLE_NAME)
        self.mapper = RateHistoryMapper()

    async def save(self, rate_history: RateHistory) -> RateHistory:
        item = self.mapper.to_dynamodb(rate_history)
        self.table.put_item(Item=item)
        logger.info(
            "rate_history_saved",
            currency_code=rate_history.currency_code,
            timestamp=rate_history.timestamp.isoformat(),
        )
        return rate_history

    async def save_batch(self, rates: List[RateHistory]) -> int:
        saved_count = 0

        with self.table.batch_writer() as batch:
            for rate in rates:
                item = self.mapper.to_dynamodb(rate)
                batch.put_item(Item=item)
                saved_count += 1

        logger.info("rate_history_batch_saved", count=saved_count)
        return saved_count

    async def find_by_currency_range(
        self,
        currency_code: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100,
    ) -> List[RateHistory]:
        try:
            response = self.table.query(
                KeyConditionExpression=Key("currency_code").eq(currency_code.upper())
                & Key("timestamp").between(
                    start_date.isoformat(),
                    end_date.isoformat(),
                ),
                ScanIndexForward=False,  # Newest first
                Limit=limit,
            )

            items = response.get("Items", [])
            logger.info(
                "rate_history_query",
                currency_code=currency_code,
                count=len(items),
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )
            return [self.mapper.to_entity(item) for item in items]

        except Exception as e:
            logger.error("rate_history_query_error", error=str(e))
            return []

    async def find_latest(self, currency_code: str) -> Optional[RateHistory]:
        try:
            response = self.table.query(
                KeyConditionExpression=Key("currency_code").eq(currency_code.upper()),
                ScanIndexForward=False,  # Newest first
                Limit=1,
            )

            items = response.get("Items", [])
            if not items:
                return None

            return self.mapper.to_entity(items[0])

        except Exception as e:
            logger.error("rate_history_find_latest_error", error=str(e))
            return None


__all__ = ["DynamoDBRateHistoryRepository"]
