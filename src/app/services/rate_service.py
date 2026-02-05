from datetime import datetime, UTC, timedelta
from typing import Optional, List
import boto3
from decimal import Decimal

from app.clients.exchange_rate_client import KoreaEximExchangeRateClient, ExchangeRate
from app.core.config import settings
from app.domain.entities.rate_history import RateHistory
from app.infrastructure.persistence.dynamodb_rate_history_repository import DynamoDBRateHistoryRepository
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class RateService:
    CACHE_TTL_HOURS = 6

    def __init__(self):
        dynamodb = boto3.resource("dynamodb")
        self.table = dynamodb.Table(settings.EXCHANGE_RATES_TABLE_NAME)
        self.api_client = KoreaEximExchangeRateClient()
        self.history_repo = DynamoDBRateHistoryRepository()

    async def get_all_rates(self) -> tuple[List[ExchangeRate], bool, Optional[datetime]]:
        cached_data = self._get_from_cache()

        if cached_data:
            rates, cache_time = cached_data
            logger.info("cache_hit", currency_count=len(rates))
            return rates, True, cache_time

        logger.info("cache_miss_fetching_from_api")
        rates = self.api_client.fetch_rates()

        if rates:
            self._save_to_cache(rates)
            logger.info("rates_cached", currency_count=len(rates))
        
        return rates, False, None

    async def get_rate_by_currency(self, currency_code: str) -> Optional[ExchangeRate]:
        all_rates, _, _ = await self.get_all_rates()

        currency_upper = currency_code.upper()
        for rate in all_rates:
            if rate.cur_unit.upper() == currency_upper:
                return rate

        logger.warning("currency_not_found", currency_code=currency_code)
        return None

    async def get_rate_history(
        self,
        currency_code: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100,
    ) -> List[RateHistory]:
        history = await self.history_repo.find_by_currency_range(
            currency_code=currency_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        logger.info(
            "rate_history_fetched",
            currency_code=currency_code,
            count=len(history),
        )
        return history

    async def get_latest_rate_history(self, currency_code: str) -> Optional[RateHistory]:
        return await self.history_repo.find_latest(currency_code)

    def _get_from_cache(self) -> Optional[tuple[List[ExchangeRate], datetime]]:
        try:
            response = self.table.get_item(Key={"currency_code": "CACHE_ALL"})
            item = response.get("Item")

            if not item:
                return None

            cache_time = datetime.fromisoformat(item["updated_at"])
            rates_data = item["rates"]

            rates = []
            for rate_dict in rates_data:
                rate = ExchangeRate(
                    cur_unit=rate_dict["cur_unit"],
                    cur_nm=rate_dict["cur_nm"],
                    ttb=float(rate_dict["ttb"]),
                    tts=float(rate_dict["tts"]),
                    deal_bas_r=float(rate_dict["deal_bas_r"])
                )
                rates.append(rate)

            return rates, cache_time

        except Exception as e:
            logger.error("cache_read_error", error=str(e))
            return None

    def _save_to_cache(self, rates: List[ExchangeRate]) -> None:
        try:
            now = datetime.now(UTC)
            ttl = int((now + timedelta(hours=self.CACHE_TTL_HOURS)).timestamp())
            
            rates_data = []
            for rate in rates:
                rates_data.append({
                    "cur_unit": rate.cur_unit,
                    "cur_nm": rate.cur_nm,
                    "ttb": Decimal(str(rate.ttb)),
                    "tts": Decimal(str(rate.tts)),
                    "deal_bas_r": Decimal(str(rate.deal_bas_r))
                })
            
            self.table.put_item(
                Item={
                    "currency_code": "CACHE_ALL",
                    "rates": rates_data,
                    "updated_at": now.isoformat(),
                    "ttl": ttl
                }
            )
            logger.info("cache_saved", ttl_hours=self.CACHE_TTL_HOURS)
        except Exception as e:
            logger.error("cache_write_error", error=str(e))
