import json
import os
import sys
from datetime import datetime, timedelta, UTC
import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.clients.exchange_rate_client import (
    KoreaEximExchangeRateClient,
    NoDataAvailableError,
    RateLimitExceededError,
)
from app.domain.entities.rate_history import RateHistory
from app.infrastructure.persistence.dynamodb_rate_history_repository import DynamoDBRateHistoryRepository
from app.infrastructure.logging.logger import setup_logging, get_logger

setup_logging(level="INFO")
logger = get_logger(__name__)

KOREAEXIM_AUTHKEY = os.environ.get('KOREAEXIM_AUTHKEY', '')
EVENTBRIDGE_BUS = os.environ.get('EVENTBRIDGE_BUS', 'currency-events')


async def save_rate_history(exchange_rates, source_date: str, rate_history_repo=None) -> None:
    """Save fetched rates to history table for time-series analysis."""
    if rate_history_repo is None:
        rate_history_repo = DynamoDBRateHistoryRepository()
    
    now = datetime.now(UTC)

    history_records = [
        RateHistory(
            currency_code=rate.cur_unit.upper(),
            timestamp=now,
            currency_name=rate.cur_nm,
            ttb=rate.ttb,
            tts=rate.tts,
            deal_bas_r=rate.deal_bas_r,
            source_date=source_date,
            created_at=now,
            buy_rate=rate.ttb,
            sell_rate=rate.tts,
            spread=rate.tts - rate.ttb,
        )
        for rate in exchange_rates
    ]

    saved_count = await rate_history_repo.save_batch(history_records)
    logger.info("rate_history_saved", count=saved_count, source_date=source_date)


async def fetch_rates_async():
    try:
        logger.info("starting_rate_fetch")
        
        eventbridge = boto3.client('events')
        client = KoreaEximExchangeRateClient(authkey=KOREAEXIM_AUTHKEY)

        today = datetime.now().strftime("%Y%m%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

        exchange_rates = None
        source_date = today
        try:
            exchange_rates = client.fetch_rates(searchdate=today, data="AP01")
            logger.info("rates_fetched", date=today, count=len(exchange_rates))
        except NoDataAvailableError:
            logger.info("no_data_today_trying_yesterday", today=today, yesterday=yesterday)
            exchange_rates = client.fetch_rates(searchdate=yesterday, data="AP01")
            source_date = yesterday
            logger.info("rates_fetched", date=yesterday, count=len(exchange_rates))
        except RateLimitExceededError as e:
            logger.error("rate_limit_exceeded", error=str(e))
            return {
                'statusCode': 429,
                'body': json.dumps({'error': 'API rate limit exceeded (1000 calls/day)'})
            }
        
        if not exchange_rates:
            logger.warning("no_exchange_rates")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No exchange rates available'})
            }
        
        rates_by_currency = {}
        for rate in exchange_rates:
            currency_code = rate.cur_unit.upper()
            rates_by_currency[currency_code] = {
                'cur_unit': rate.cur_unit,
                'cur_nm': rate.cur_nm,
                'TTS': rate.tts,
                'TTB': rate.ttb,
                'DEAL_BAS_R': rate.deal_bas_r
            }

        # Save to rate history for time-series analysis
        await save_rate_history(exchange_rates, source_date)

        logger.info(
            "publishing_event",
            currency_count=len(rates_by_currency),
            currencies=list(rates_by_currency.keys())
        )
        
        eventbridge.put_events(
            Entries=[{
                'Source': 'currency.tracker',
                'DetailType': 'Rate Updated',
                'Detail': json.dumps({
                    'base_currency': 'KRW',
                    'rates': rates_by_currency,
                    'timestamp': datetime.now(UTC).isoformat()
                }),
                'EventBusName': EVENTBRIDGE_BUS
            }]
        )
        
        logger.info("rate_fetch_completed", currency_count=len(rates_by_currency))
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Fetched rates for {len(rates_by_currency)} currencies',
                'currencies': list(rates_by_currency.keys())
            })
        }
        
    except Exception as e:
        logger.error("rate_fetch_error", error=str(e), exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Failed to fetch rates: {str(e)}'})
        }


def lambda_handler(event, context):
    if hasattr(context, 'aws_request_id'):
        logger.info(
            "lambda_invoked",
            extra={
                "aws_request_id": context.aws_request_id,
                "function_name": context.function_name,
            }
        )
    
    try:
        import asyncio
        return asyncio.run(fetch_rates_async())
    except Exception as e:
        logger.error("lambda_handler_error", error=str(e), exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
