from typing import Any, Optional

from telegram import Bot
from telegram.request import HTTPXRequest

from app.domain.notification import NotificationService
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class TelegramNotificationService(NotificationService):
    """Sends Telegram messages on behalf of a user.

    ``metadata`` must contain ``chat_id`` — the Telegram chat ID for the recipient.
    """

    def __init__(self, token: str) -> None:
        request = HTTPXRequest(
            connection_pool_size=2,
            read_timeout=5.0,
            write_timeout=5.0,
            connect_timeout=5.0,
        )
        self._bot: Optional[Bot] = Bot(token=token, request=request) if token else None

    async def send(self, user_id: str, message: str, metadata: dict[str, Any]) -> bool:
        chat_id: Optional[str] = metadata.get("chat_id")
        if not chat_id:
            logger.warning("telegram_send_skipped", user_id=user_id, reason="no_chat_id")
            return False
        if not self._bot:
            logger.warning("telegram_bot_not_configured", user_id=user_id)
            return False
        try:
            await self._bot.send_message(chat_id=chat_id, text=message)
            logger.info("telegram_message_sent", user_id=user_id, chat_id=chat_id)
            return True
        except Exception as exc:
            logger.error("telegram_send_failed", user_id=user_id, chat_id=chat_id, error=str(exc))
            return False

    async def close(self) -> None:
        if self._bot:
            await self._bot.close()
