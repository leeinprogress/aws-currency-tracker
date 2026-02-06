import pytest
import uuid
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, patch

from app.domain.entities.alert import Alert
from app.domain.entities.rate_history import RateHistory
from functions.weekly_report import (
    calculate_weekly_stats,
    format_report_message,
    generate_weekly_report_async,
    WeeklyStats,
)


def create_rate_history(
    currency_code: str,
    timestamp: datetime,
    deal_bas_r: float,
    currency_name: str = "US Dollar",
) -> RateHistory:
    return RateHistory(
        currency_code=currency_code,
        timestamp=timestamp,
        currency_name=currency_name,
        ttb=deal_bas_r - 10,
        tts=deal_bas_r + 10,
        deal_bas_r=deal_bas_r,
        source_date=timestamp.strftime("%Y%m%d"),
    )


def create_alert(
    user_id: str,
    chat_id: str,
    currency: str = "USD",
    is_active: bool = True,
) -> Alert:
    return Alert(
        alert_id=str(uuid.uuid4()),
        user_id=user_id,
        telegram_chat_id=chat_id,
        target_currency=currency,
        target_rate=1350.0,
        condition="above",
        rate_type="TTS",
        is_active=is_active,
    )


class TestCalculateWeeklyStats:
    def test_calculates_stats_correctly(self):
        now = datetime.now(UTC)
        history = [
            create_rate_history("USD", now - timedelta(days=6), 1300.0),
            create_rate_history("USD", now - timedelta(days=4), 1320.0),
            create_rate_history("USD", now - timedelta(days=2), 1280.0),
            create_rate_history("USD", now, 1350.0),
        ]

        stats = calculate_weekly_stats("USD", history)

        assert stats is not None
        assert stats.currency_code == "USD"
        assert stats.start_rate == 1300.0
        assert stats.end_rate == 1350.0
        assert stats.high_rate == 1350.0
        assert stats.low_rate == 1280.0
        assert stats.data_points == 4
        # Change: (1350 - 1300) / 1300 * 100 = 3.846...
        assert abs(stats.change_percent - 3.846) < 0.01

    def test_returns_none_for_empty_history(self):
        stats = calculate_weekly_stats("USD", [])
        assert stats is None

    def test_returns_none_for_single_record(self):
        history = [create_rate_history("USD", datetime.now(UTC), 1300.0)]
        stats = calculate_weekly_stats("USD", history)
        assert stats is None

    def test_handles_negative_change(self):
        now = datetime.now(UTC)
        history = [
            create_rate_history("USD", now - timedelta(days=3), 1400.0),
            create_rate_history("USD", now, 1300.0),
        ]

        stats = calculate_weekly_stats("USD", history)

        assert stats is not None
        assert stats.change_percent < 0
        # Change: (1300 - 1400) / 1400 * 100 = -7.14...
        assert abs(stats.change_percent - (-7.14)) < 0.01


class TestFormatReportMessage:
    def test_formats_single_currency_report(self):
        start_date = datetime(2024, 2, 1, tzinfo=UTC)
        end_date = datetime(2024, 2, 7, tzinfo=UTC)

        stats_list = [
            WeeklyStats(
                currency_code="USD",
                currency_name="US Dollar",
                start_rate=1300.0,
                end_rate=1350.0,
                high_rate=1360.0,
                low_rate=1290.0,
                change_percent=3.85,
                data_points=7,
            )
        ]

        message = format_report_message(stats_list, start_date, end_date)

        assert "Weekly Exchange Rate Report" in message
        assert "02/01 - 02/07" in message
        assert "USD" in message
        assert "US Dollar" in message
        assert "+3.85%" in message
        assert "1,300.00" in message
        assert "1,350.00" in message

    def test_formats_multiple_currencies(self):
        start_date = datetime(2024, 2, 1, tzinfo=UTC)
        end_date = datetime(2024, 2, 7, tzinfo=UTC)

        stats_list = [
            WeeklyStats("USD", "US Dollar", 1300, 1350, 1360, 1290, 3.85, 7),
            WeeklyStats("EUR", "Euro", 1400, 1380, 1420, 1370, -1.43, 7),
        ]

        message = format_report_message(stats_list, start_date, end_date)

        assert "USD" in message
        assert "EUR" in message
        assert "📈" in message  # Positive change
        assert "📉" in message  # Negative change


@pytest.mark.asyncio
class TestGenerateWeeklyReportAsync:
    @patch("functions.weekly_report.get_alert_repository")
    @patch("functions.weekly_report.DynamoDBRateHistoryRepository")
    @patch("functions.weekly_report.get_telegram_bot")
    async def test_no_alerts_returns_early(
        self, mock_bot, mock_history_repo, mock_alert_repo
    ):
        mock_repo = AsyncMock()
        mock_repo.find_all_active.return_value = []
        mock_alert_repo.return_value = mock_repo

        result = await generate_weekly_report_async({})

        assert result["statusCode"] == 200
        assert "No active alerts" in result["body"]

    @patch("functions.weekly_report.get_alert_repository")
    @patch("functions.weekly_report.DynamoDBRateHistoryRepository")
    @patch("functions.weekly_report.get_telegram_bot")
    async def test_sends_reports_to_users(
        self, mock_bot, mock_history_repo_class, mock_alert_repo
    ):
        # Setup alerts
        mock_repo = AsyncMock()
        mock_repo.find_all_active.return_value = [
            create_alert("user-1", "chat-1", "USD"),
            create_alert("user-1", "chat-1", "EUR"),
            create_alert("user-2", "chat-2", "USD"),
        ]
        mock_alert_repo.return_value = mock_repo

        # Setup rate history
        now = datetime.now(UTC)
        mock_history_repo = AsyncMock()
        mock_history_repo.find_by_currency_range.return_value = [
            create_rate_history("USD", now - timedelta(days=3), 1300.0),
            create_rate_history("USD", now, 1350.0),
        ]
        mock_history_repo_class.return_value = mock_history_repo

        # Setup Telegram bot
        mock_telegram_bot = AsyncMock()
        mock_telegram_bot.send_message = AsyncMock()
        mock_telegram_bot.close = AsyncMock()
        mock_bot.return_value = mock_telegram_bot

        result = await generate_weekly_report_async({})

        assert result["statusCode"] == 200
        # Should send to 2 unique chat_ids
        assert mock_telegram_bot.send_message.call_count == 2

    @patch("functions.weekly_report.get_alert_repository")
    @patch("functions.weekly_report.DynamoDBRateHistoryRepository")
    @patch("functions.weekly_report.get_telegram_bot")
    async def test_handles_no_rate_data(
        self, mock_bot, mock_history_repo_class, mock_alert_repo
    ):
        mock_repo = AsyncMock()
        mock_repo.find_all_active.return_value = [
            create_alert("user-1", "chat-1", "USD"),
        ]
        mock_alert_repo.return_value = mock_repo

        mock_history_repo = AsyncMock()
        mock_history_repo.find_by_currency_range.return_value = []
        mock_history_repo_class.return_value = mock_history_repo

        mock_bot.return_value = None

        result = await generate_weekly_report_async({})

        assert result["statusCode"] == 200
        assert "No rate data" in result["body"]
