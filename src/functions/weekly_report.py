import asyncio
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import Any, Dict, List, Optional, Tuple

from telegram import Bot
from telegram.request import HTTPXRequest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.domain.entities.rate_history import RateHistory
from app.infrastructure.logging.logger import get_logger, setup_logging
from app.infrastructure.persistence.dynamodb_rate_history_repository import (
    DynamoDBRateHistoryRepository,
)
from app.infrastructure.persistence.repositories import get_alert_repository

setup_logging(level="INFO")
logger = get_logger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


@dataclass
class WeeklyStats:
    """Statistics for a currency over the past week."""
    currency_code: str
    currency_name: str
    start_rate: float
    end_rate: float
    high_rate: float
    low_rate: float
    change_percent: float
    data_points: int


def get_telegram_bot() -> Optional[Bot]:
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("telegram_bot_not_configured")
        return None
    request = HTTPXRequest(
        connection_pool_size=2, read_timeout=10.0, write_timeout=10.0, connect_timeout=5.0
    )
    return Bot(token=TELEGRAM_BOT_TOKEN, request=request)


async def send_telegram_message(bot: Optional[Bot], chat_id: str, message: str) -> bool:
    if not bot:
        return False
    try:
        await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
        return True
    except Exception as e:
        logger.error("telegram_send_failed", chat_id=chat_id, error=str(e))
        return False


def calculate_weekly_stats(
    currency_code: str,
    history: List[RateHistory],
) -> Optional[WeeklyStats]:
    """Calculate statistics from rate history records."""
    if not history or len(history) < 2:
        return None

    # History is sorted newest first, so reverse for chronological order
    sorted_history = sorted(history, key=lambda r: r.timestamp)

    rates = [r.deal_bas_r for r in sorted_history]
    start_rate = rates[0]
    end_rate = rates[-1]

    if start_rate == 0:
        return None

    change_percent = ((end_rate - start_rate) / start_rate) * 100

    return WeeklyStats(
        currency_code=currency_code,
        currency_name=sorted_history[0].currency_name,
        start_rate=start_rate,
        end_rate=end_rate,
        high_rate=max(rates),
        low_rate=min(rates),
        change_percent=change_percent,
        data_points=len(history),
    )


def format_report_message(
    stats_list: List[WeeklyStats],
    start_date: datetime,
    end_date: datetime,
) -> str:
    """Format weekly stats into a readable Telegram message."""
    date_range = f"{start_date.strftime('%m/%d')} - {end_date.strftime('%m/%d')}"

    lines = [
        "<b>📊 Weekly Exchange Rate Report</b>",
        f"<i>{date_range}</i>",
        "",
    ]

    for stats in stats_list:
        trend = "📈" if stats.change_percent > 0 else "📉" if stats.change_percent < 0 else "➡️"

        lines.extend([
            f"<b>{stats.currency_code}</b> ({stats.currency_name})",
            f"  {trend} {stats.change_percent:+.2f}%",
            f"  Start: {stats.start_rate:,.2f} → End: {stats.end_rate:,.2f}",
            f"  High: {stats.high_rate:,.2f} / Low: {stats.low_rate:,.2f}",
            "",
        ])

    lines.append("💡 Based on DEAL_BAS_R (기준환율)")

    return "\n".join(lines)


async def generate_weekly_report_async(event: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("starting_weekly_report")

    # Get all active alerts to find users and their interested currencies
    alert_repo = get_alert_repository()
    alerts = await alert_repo.find_all_active()

    if not alerts:
        logger.info("no_active_alerts_for_report")
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "No active alerts, no reports to send"}),
        }

    # Group alerts by user (using telegram_chat_id as identifier)
    user_currencies: Dict[str, set] = defaultdict(set)
    for alert in alerts:
        user_currencies[alert.telegram_chat_id].add(alert.target_currency.upper())

    logger.info(
        "users_and_currencies_loaded",
        user_count=len(user_currencies),
        total_alerts=len(alerts),
    )

    # Calculate date range for the past week
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=7)

    # Fetch rate history for all unique currencies
    all_currencies = set()
    for currencies in user_currencies.values():
        all_currencies.update(currencies)

    rate_history_repo = DynamoDBRateHistoryRepository()

    async def _fetch_and_calc_stats(currency_code: str) -> Optional[Tuple[str, WeeklyStats]]:
        """Helper to fetch history and calculate stats for one currency."""
        history = await rate_history_repo.find_by_currency_range(
            currency_code=currency_code,
            start_date=start_date,
            end_date=end_date,
            limit=500,
        )
        stats = calculate_weekly_stats(currency_code, history)
        if stats:
            logger.debug(
                "currency_stats_calculated",
                currency=currency_code,
                change_percent=round(stats.change_percent, 2),
            )
            return currency_code, stats
        return None

    # Concurrently fetch and calculate stats for all currencies
    tasks = [_fetch_and_calc_stats(code) for code in all_currencies]
    results = await asyncio.gather(*tasks)

    currency_stats: Dict[str, WeeklyStats] = {
        code: stats for result in results if result for code, stats in [result]
    }

    if not currency_stats:
        logger.warning("no_rate_data_for_report")
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "No rate data available for report"}),
        }

    # Send personalized reports to each user
    bot = get_telegram_bot()
    reports_sent = 0
    reports_failed = 0

    try:
        for chat_id, currencies in user_currencies.items():
            # Get stats for this user's currencies only
            user_stats = [
                currency_stats[c] for c in currencies if c in currency_stats
            ]

            if not user_stats:
                continue

            # Sort by absolute change (most volatile first)
            user_stats.sort(key=lambda s: abs(s.change_percent), reverse=True)

            message = format_report_message(user_stats, start_date, end_date)

            if await send_telegram_message(bot, chat_id, message):
                reports_sent += 1
                logger.info("weekly_report_sent", chat_id=chat_id, currencies=len(user_stats))
            else:
                reports_failed += 1

    finally:
        if bot:
            await bot.close()

    logger.info(
        "weekly_report_completed",
        reports_sent=reports_sent,
        reports_failed=reports_failed,
        total_users=len(user_currencies),
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Weekly reports generated",
            "reports_sent": reports_sent,
            "reports_failed": reports_failed,
            "currencies_analyzed": len(currency_stats),
        }),
    }


def lambda_handler(event: Dict[str, Any], context: object) -> Dict[str, Any]:
    if hasattr(context, "aws_request_id"):
        logger.info(
            "lambda_invoked",
            aws_request_id=context.aws_request_id,
            function_name=context.function_name,
        )

    try:
        return asyncio.run(generate_weekly_report_async(event))
    except Exception as e:
        logger.error("lambda_handler_error", error=str(e), exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
