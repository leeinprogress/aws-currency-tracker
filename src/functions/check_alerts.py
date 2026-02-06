import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, UTC
from typing import Any, Dict, List, Optional, Tuple

from telegram import Bot
from telegram.request import HTTPXRequest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.domain.entities.alert import Alert
from app.infrastructure.logging.logger import get_logger, setup_logging
from app.infrastructure.persistence.dynamodb_notification_history_repository import (
    DynamoDBNotificationHistoryRepository,
)
from app.infrastructure.persistence.dynamodb_rate_history_repository import (
    DynamoDBRateHistoryRepository,
)
from app.infrastructure.persistence.repositories import get_alert_repository

setup_logging(level="INFO")
logger = get_logger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
VOLATILITY_THRESHOLD = 2.0


def _parse_event(event: Dict[str, Any]) -> Tuple[str, Dict[str, Any], str]:
    logger.debug("parsing_event", event_obj=event)
    detail = event.get("detail", {})
    if isinstance(detail, str):
        try:
            detail = json.loads(detail)
        except json.JSONDecodeError as e:
            raise ValueError("Event detail is a string but not valid JSON") from e

    base_currency = detail.get("base_currency")
    rates = detail.get("rates", {})
    timestamp = detail.get("timestamp", datetime.now(UTC).isoformat())

    if not base_currency or not rates:
        raise ValueError("Missing base_currency or rates in event detail")

    return base_currency, rates, timestamp


def get_telegram_bot() -> Optional[Bot]:
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("telegram_bot_not_configured")
        return None
    request = HTTPXRequest(
        connection_pool_size=2, read_timeout=5.0, write_timeout=5.0, connect_timeout=5.0
    )
    return Bot(token=TELEGRAM_BOT_TOKEN, request=request)


async def send_telegram_message(
    bot: Optional[Bot], chat_id: str, message: str
) -> bool:
    if not bot:
        logger.warning("telegram_bot_not_available_for_sending")
        return False
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        return True
    except Exception as e:
        logger.error("telegram_send_failed", chat_id=chat_id, error=str(e))
        return False


async def _check_target_alerts_for_currency(
    currency_code: str,
    currency_data: Dict[str, Any],
    alerts_for_currency: List[Alert],
    timestamp: str,
    bot: Optional[Bot],
    notification_repo: Optional[DynamoDBNotificationHistoryRepository] = None,
) -> List[str]:
    triggered_alerts = []
    for alert in alerts_for_currency:
        rate_type = alert.rate_type.upper()
        current_rate = float(currency_data.get(rate_type, 0))
        if current_rate == 0:
            continue

        target_rate = alert.target_rate
        condition = alert.condition.lower()
        should_alert = (condition == "above" and current_rate >= target_rate) or (
            condition == "below" and current_rate <= target_rate
        )

        if should_alert:
            message = (
                f"🔔 Target Rate Reached!\n\n"
                f"📊 {currency_code} ({currency_data.get('cur_nm', '')})\n"
                f"🎯 Target: {target_rate:,.2f} ({condition})\n"
                f"💰 Current ({rate_type}): {current_rate:,.2f}\n"
                f"⏰ {timestamp}"
            )
            if await send_telegram_message(bot, alert.telegram_chat_id, message):
                triggered_alerts.append(alert.alert_id)
                logger.info(
                    "target_alert_sent",
                    alert_id=alert.alert_id,
                    chat_id=alert.telegram_chat_id,
                )
                if notification_repo:
                    try:
                        await notification_repo.save({
                            "user_id": alert.user_id,
                            "alert_id": alert.alert_id,
                            "currency": currency_code,
                            "target_rate": target_rate,
                            "actual_rate": current_rate,
                            "direction": condition,
                            "channel": "telegram",
                            "triggered_at": datetime.now(UTC).isoformat(),
                        })
                    except Exception as exc:
                        logger.error("notification_history_save_failed", error=str(exc))
    return triggered_alerts


async def _check_volatility_for_currency(
    currency_code: str,
    currency_data: Dict[str, Any],
    alerts_for_currency: List[Alert],
    timestamp: str,
    bot: Optional[Bot],
    rate_history_repo: DynamoDBRateHistoryRepository,
) -> List[Dict[str, Any]]:
    current_rate = float(currency_data.get("DEAL_BAS_R", 0))
    if current_rate == 0:
        return []

    try:
        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)
        history = await rate_history_repo.find_by_currency_range(
            currency_code=currency_code,
            start_date=yesterday - timedelta(hours=12),
            end_date=yesterday + timedelta(hours=12),
            limit=1,
        )

        if not history or history[0].deal_bas_r == 0:
            logger.debug("no_valid_previous_rate", currency=currency_code)
            return []

        previous_rate = history[0].deal_bas_r
        change_percent = ((current_rate - previous_rate) / previous_rate) * 100

        if abs(change_percent) >= VOLATILITY_THRESHOLD:
            direction = "📈 Surge" if change_percent > 0 else "📉 Drop"
            logger.info(
                "volatility_detected",
                currency=currency_code,
                change=round(change_percent, 2),
            )

            message = (
                f"{direction} Alert!\n\n"
                f"📊 {currency_code} ({currency_data.get('cur_nm', '')})\n"
                f"💹 Change: {change_percent:+.2f}%\n"
                f"💰 Current: {current_rate:,.2f} KRW\n"
                f"📅 Previous: {previous_rate:,.2f} KRW\n"
                f"⏰ {timestamp}"
            )

            notified_chat_ids = set()
            volatility_notifications = []
            for alert in alerts_for_currency:
                if alert.telegram_chat_id not in notified_chat_ids:
                    if await send_telegram_message(bot, alert.telegram_chat_id, message):
                        notified_chat_ids.add(alert.telegram_chat_id)
                        notification_info = {
                            "currency": currency_code,
                            "chat_id": alert.telegram_chat_id,
                            "change_percent": round(change_percent, 2),
                        }
                        volatility_notifications.append(notification_info)
                        logger.info("volatility_alert_sent", **notification_info)
            return volatility_notifications

    except Exception as e:
        logger.error("volatility_check_error", currency=currency_code, error=str(e))

    return []


async def check_alerts_async(event: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("starting_alert_check", event_source=event.get("source", "unknown"))
    try:
        base_currency, rates, timestamp = _parse_event(event)
    except ValueError as e:
        logger.error("invalid_event_format", error=str(e), event=str(event)[:200])
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(e), "received": str(event)[:200]}),
        }

    alert_repo = get_alert_repository()
    alerts = await alert_repo.find_all_active()
    logger.info(
        "loaded_active_alerts",
        base_currency=base_currency,
        alert_count=len(alerts),
    )

    alerts_by_currency = defaultdict(list)
    for alert in alerts:
        alerts_by_currency[alert.target_currency.upper()].append(alert)

    bot = get_telegram_bot()
    rate_history_repo = DynamoDBRateHistoryRepository()
    notification_repo = DynamoDBNotificationHistoryRepository()
    all_triggered_alerts: List[str] = []
    all_volatility_notifications: List[Dict[str, Any]] = []

    try:
        for currency_code, currency_data in rates.items():
            if not isinstance(currency_data, dict):
                continue

            alerts_for_currency = alerts_by_currency.get(currency_code, [])
            if not alerts_for_currency:
                continue

            triggered = await _check_target_alerts_for_currency(
                currency_code, currency_data, alerts_for_currency, timestamp, bot,
                notification_repo=notification_repo,
            )
            all_triggered_alerts.extend(triggered)

            volatility = await _check_volatility_for_currency(
                currency_code,
                currency_data,
                alerts_for_currency,
                timestamp,
                bot,
                rate_history_repo,
            )
            all_volatility_notifications.extend(volatility)

    finally:
        if bot:
            await bot.close()

    logger.info(
        "alert_check_completed",
        total_alerts=len(alerts),
        target_triggered=len(all_triggered_alerts),
        volatility_notifications=len(all_volatility_notifications),
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": f"Checked {len(alerts)} alerts",
                "target_triggered": len(all_triggered_alerts),
                "volatility_notifications": len(all_volatility_notifications),
                "triggered_alert_ids": all_triggered_alerts,
            }
        ),
    }


def lambda_handler(event: Dict[str, Any], context: object) -> Dict[str, Any]:
    if hasattr(context, "aws_request_id"):
        logger.info(
            "lambda_invoked",
            aws_request_id=context.aws_request_id,
            function_name=context.function_name,
        )

    try:
        return asyncio.run(check_alerts_async(event))
    except Exception as e:
        logger.error("lambda_handler_error", error=str(e), exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
