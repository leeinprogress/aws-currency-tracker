from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from app.domain.entities.alert import Alert
from app.domain.entities.user import User
from app.domain.entities.rate_history import RateHistory


class AlertMapper:
    @staticmethod
    def to_dynamodb(alert: Alert) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "alert_id": alert.alert_id,
            "user_id": alert.user_id,
            "telegram_chat_id": alert.telegram_chat_id,
            "target_currency": alert.target_currency,
            "target_rate": Decimal(str(alert.target_rate)),
            "condition": alert.condition,
            "rate_type": alert.rate_type,
            "is_active": alert.is_active,
        }

        # Sparse index attribute: only present for active alerts
        if alert.is_active:
            item["active_user_id"] = alert.user_id

        if alert.idempotency_key is not None:
            item["idempotency_key"] = alert.idempotency_key

        if alert.created_at:
            item["created_at"] = alert.created_at.isoformat()
        if alert.updated_at:
            item["updated_at"] = alert.updated_at.isoformat()

        return item

    @staticmethod
    def to_entity(item: Dict[str, Any]) -> Alert:
        return Alert(
            alert_id=item["alert_id"],
            user_id=item["user_id"],
            telegram_chat_id=item["telegram_chat_id"],
            target_currency=item["target_currency"],
            target_rate=float(item["target_rate"]),
            condition=item["condition"],
            rate_type=item["rate_type"],
            is_active=item["is_active"],
            idempotency_key=item.get("idempotency_key"),
            created_at=datetime.fromisoformat(item["created_at"]) if "created_at" in item else None,
            updated_at=datetime.fromisoformat(item["updated_at"]) if "updated_at" in item else None,
        )


class UserMapper:
    @staticmethod
    def to_dynamodb(user: User) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "user_id": user.user_id,
            "email": user.email,
            "is_active": user.is_active,
            "auth_provider": user.auth_provider,
        }

        if user.telegram_chat_id is not None:
            item["telegram_chat_id"] = user.telegram_chat_id
        if user.hashed_password is not None:
            item["hashed_password"] = user.hashed_password
        # google_id is sparse — only store when present
        if user.google_id is not None:
            item["google_id"] = user.google_id
        if user.refresh_token_hash is not None:
            item["refresh_token_hash"] = user.refresh_token_hash
        if user.created_at:
            item["created_at"] = user.created_at.isoformat()
        if user.updated_at:
            item["updated_at"] = user.updated_at.isoformat()

        return item

    @staticmethod
    def to_entity(item: Dict[str, Any]) -> User:
        return User(
            user_id=item["user_id"],
            email=item["email"],
            is_active=item["is_active"],
            auth_provider=item.get("auth_provider", "local"),
            telegram_chat_id=item.get("telegram_chat_id"),
            hashed_password=item.get("hashed_password"),
            google_id=item.get("google_id"),
            refresh_token_hash=item.get("refresh_token_hash"),
            created_at=datetime.fromisoformat(item["created_at"]) if "created_at" in item else None,
            updated_at=datetime.fromisoformat(item["updated_at"]) if "updated_at" in item else None,
        )


class RateHistoryMapper:
    @staticmethod
    def to_dynamodb(rate: RateHistory, ttl_days: int = 90) -> Dict[str, Any]:
        from datetime import timedelta, UTC

        now = datetime.now(UTC)
        ttl = int((now + timedelta(days=ttl_days)).timestamp())

        buy = rate.buy_rate if rate.buy_rate is not None else rate.ttb
        sell = rate.sell_rate if rate.sell_rate is not None else rate.tts
        spread = rate.spread if rate.spread is not None else (sell - buy)

        return {
            "currency_code": rate.currency_code,
            "timestamp": rate.timestamp.isoformat(),
            "currency_name": rate.currency_name,
            "ttb": Decimal(str(rate.ttb)),
            "tts": Decimal(str(rate.tts)),
            "deal_bas_r": Decimal(str(rate.deal_bas_r)),
            "buy_rate": Decimal(str(buy)),
            "sell_rate": Decimal(str(sell)),
            "spread": Decimal(str(spread)),
            "source_date": rate.source_date,
            "created_at": (rate.created_at or now).isoformat(),
            "ttl": ttl,
        }

    @staticmethod
    def to_entity(item: Dict[str, Any]) -> RateHistory:
        ttb = float(item["ttb"])
        tts = float(item["tts"])
        buy = float(item["buy_rate"]) if "buy_rate" in item else ttb
        sell = float(item["sell_rate"]) if "sell_rate" in item else tts
        spread = float(item["spread"]) if "spread" in item else (sell - buy)

        return RateHistory(
            currency_code=item["currency_code"],
            timestamp=datetime.fromisoformat(item["timestamp"]),
            currency_name=item["currency_name"],
            ttb=ttb,
            tts=tts,
            deal_bas_r=float(item["deal_bas_r"]),
            source_date=item["source_date"],
            created_at=datetime.fromisoformat(item["created_at"]) if "created_at" in item else None,
            buy_rate=buy,
            sell_rate=sell,
            spread=spread,
        )
