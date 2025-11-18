
import json
import pytest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

from app.db.models.alert import Alert
from app.clients.exchange_rate_client import ExchangeRate
from functions.check_alerts import check_alerts_async
from functions.fetch_rates import fetch_rates_async

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_telegram_bot():
    """Fixture to mock the telegram bot."""
    with patch('functions.check_alerts.bot', new_callable=MagicMock) as mock_bot:
        # Make sure the bot object itself is truthy
        mock_bot.send_message = MagicMock()
        yield mock_bot

async def test_check_alerts_handler_triggers_one_alert(alerts_table, mock_telegram_bot):
    """
    Test the check_alerts lambda handler, ensuring it correctly identifies
    and triggers a single valid alert.
    """
    # 1. Setup: Create alerts in the mock database
    user_id = "test-user-lambda"
    chat_id = "test-chat-lambda"
    
    # This alert SHOULD be triggered
    alert_to_trigger = Alert(
        alert_id=str(uuid.uuid4()),
        user_id=user_id,
        telegram_chat_id=chat_id,
        base_currency="USD",
        target_currency="KRW",
        target_rate=1300.0,
        condition="above",
        rate_type="TTS",
        is_active=True,
    )
    
    # This alert should NOT be triggered (condition not met)
    alert_not_triggered = Alert(
        alert_id=str(uuid.uuid4()),
        user_id=user_id,
        telegram_chat_id=chat_id,
        base_currency="USD",
        target_currency="KRW",
        target_rate=1400.0,
        condition="above",
        rate_type="TTS",
        is_active=True,
    )
    
    # This alert should NOT be triggered (inactive)
    inactive_alert = Alert(
        alert_id=str(uuid.uuid4()),
        user_id=user_id,
        telegram_chat_id=chat_id,
        base_currency="USD",
        target_currency="KRW",
        target_rate=1200.0,
        condition="above",
        rate_type="TTS",
        is_active=False,
    )

    # Use boto3 resource to put items, which is what the repository uses
    import boto3
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(alerts_table)
    table.put_item(Item=alert_to_trigger.to_dict())
    table.put_item(Item=alert_not_triggered.to_dict())
    table.put_item(Item=inactive_alert.to_dict())

    # 2. Prepare the EventBridge event
    event = {
        "source": "currency.tracker",
        "detail-type": "Rate Updated",
        "detail": json.dumps({
            "base_currency": "USD",
            "rates": {
                "KRW": {
                    "TTS": "1350.50",
                    "TTB": "1290.00",
                    "cur_nm": "South Korean Won"
                }
            },
            "timestamp": "2025-11-18T12:00:00Z"
        })
    }

    # 3. Invoke the async function directly
    response = await check_alerts_async(event)

    # 4. Assertions
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "Checked 2 alerts"  # Only active alerts are checked
    assert body["triggered"] == 1
    assert body["alert_ids"][0] == alert_to_trigger.alert_id

    # Assert that the telegram bot was called once
    mock_telegram_bot.send_message.assert_called_once()
    
    # Assert the content of the message
    call_args = mock_telegram_bot.send_message.call_args
    assert call_args.kwargs['chat_id'] == chat_id
    assert "Currency Alert Triggered!" in call_args.kwargs['text']
    assert "Target: 1300.0 (above)" in call_args.kwargs['text']
    assert "Current Rate (TTS): 1350.5" in call_args.kwargs['text']


# ==================== Fetch Rates Function Tests ====================

@pytest.fixture
def mock_alert_repository():
    """Fixture to mock the alert repository."""
    mock_repo = MagicMock()
    mock_repo.list_alerts = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_exchange_rate_client():
    """Fixture to mock the KoreaExim exchange rate client."""
    with patch('functions.fetch_rates.KoreaEximExchangeRateClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_eventbridge():
    """Fixture to mock EventBridge client."""
    with patch('functions.fetch_rates.eventbridge') as mock_eb:
        yield mock_eb


async def test_fetch_rates_no_active_alerts(
    mock_alert_repository,
    mock_exchange_rate_client,
    mock_eventbridge,
):
    """Test fetch_rates when there are no active alerts."""
    # Setup: No active alerts
    mock_alert_repository.list_alerts.return_value = []
    
    with patch('functions.fetch_rates.get_alert_repository', return_value=mock_alert_repository):
        response = await fetch_rates_async()
    
    # Assertions
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "No active alerts to process"
    
    # Should not call exchange rate client or EventBridge
    mock_exchange_rate_client.fetch_rates.assert_not_called()
    mock_eventbridge.put_events.assert_not_called()


async def test_fetch_rates_no_exchange_rates(
    mock_alert_repository,
    mock_exchange_rate_client,
    mock_eventbridge,
):
    """Test fetch_rates when exchange rate API returns no data."""
    # Setup: Active alerts exist but no exchange rates
    active_alert = Alert(
        alert_id=str(uuid.uuid4()),
        user_id="user-123",
        telegram_chat_id="chat-123",
        base_currency="KRW",
        target_currency="USD",
        target_rate=1300.0,
        condition="above",
        rate_type="TTS",
        is_active=True,
    )
    mock_alert_repository.list_alerts.return_value = [active_alert]
    mock_exchange_rate_client.fetch_rates.return_value = []
    
    with patch('functions.fetch_rates.get_alert_repository', return_value=mock_alert_repository):
        response = await fetch_rates_async()
    
    # Assertions
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "No exchange rates available"
    
    # Should call exchange rate client but not EventBridge
    mock_exchange_rate_client.fetch_rates.assert_called_once()
    mock_eventbridge.put_events.assert_not_called()


async def test_fetch_rates_success(
    mock_alert_repository,
    mock_exchange_rate_client,
    mock_eventbridge,
):
    """Test successful fetch_rates that publishes to EventBridge."""
    # Setup: Active alerts and exchange rates
    active_alert = Alert(
        alert_id=str(uuid.uuid4()),
        user_id="user-123",
        telegram_chat_id="chat-123",
        base_currency="KRW",
        target_currency="USD",
        target_rate=1300.0,
        condition="above",
        rate_type="TTS",
        is_active=True,
    )
    mock_alert_repository.list_alerts.return_value = [active_alert]
    
    # Mock exchange rate data
    exchange_rates = [
        ExchangeRate(
            cur_unit="USD",
            cur_nm="US Dollar",
            ttb=1290.0,
            tts=1350.0,
            deal_bas_r=1320.0,
        ),
        ExchangeRate(
            cur_unit="EUR",
            cur_nm="Euro",
            ttb=1400.0,
            tts=1450.0,
            deal_bas_r=1425.0,
        ),
    ]
    mock_exchange_rate_client.fetch_rates.return_value = exchange_rates
    
    with patch('functions.fetch_rates.get_alert_repository', return_value=mock_alert_repository):
        response = await fetch_rates_async()
    
    # Assertions
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "Fetched rates for 2 currencies"
    assert body["base_currency"] == "KRW"
    assert set(body["currencies"]) == {"USD", "EUR"}
    
    # Verify EventBridge was called with correct event
    mock_eventbridge.put_events.assert_called_once()
    call_args = mock_eventbridge.put_events.call_args
    entries = call_args[1]["Entries"]
    assert len(entries) == 1
    
    event = entries[0]
    assert event["Source"] == "currency.tracker"
    assert event["DetailType"] == "Rate Updated"
    
    detail = json.loads(event["Detail"])
    assert detail["base_currency"] == "KRW"
    assert "USD" in detail["rates"]
    assert "EUR" in detail["rates"]
    assert detail["rates"]["USD"]["TTS"] == 1350.0
    assert detail["rates"]["USD"]["TTB"] == 1290.0
    assert detail["rates"]["USD"]["DEAL_BAS_R"] == 1320.0
    assert detail["rates"]["EUR"]["cur_nm"] == "Euro"
    assert "timestamp" in detail


async def test_fetch_rates_api_error(
    mock_alert_repository,
    mock_exchange_rate_client,
    mock_eventbridge,
):
    """Test fetch_rates when exchange rate API raises an error."""
    # Setup: Active alerts exist
    active_alert = Alert(
        alert_id=str(uuid.uuid4()),
        user_id="user-123",
        telegram_chat_id="chat-123",
        base_currency="KRW",
        target_currency="USD",
        target_rate=1300.0,
        condition="above",
        rate_type="TTS",
        is_active=True,
    )
    mock_alert_repository.list_alerts.return_value = [active_alert]
    
    # Mock API error
    mock_exchange_rate_client.fetch_rates.side_effect = Exception("API connection failed")
    
    with patch('functions.fetch_rates.get_alert_repository', return_value=mock_alert_repository):
        response = await fetch_rates_async()
    
    # Assertions
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Failed to fetch rates" in body["error"]
    assert "API connection failed" in body["error"]
    
    # Should not call EventBridge on error
    mock_eventbridge.put_events.assert_not_called()


async def test_fetch_rates_eventbridge_error(
    mock_alert_repository,
    mock_exchange_rate_client,
    mock_eventbridge,
):
    """Test fetch_rates when EventBridge put_events fails."""
    # Setup: Active alerts and exchange rates
    active_alert = Alert(
        alert_id=str(uuid.uuid4()),
        user_id="user-123",
        telegram_chat_id="chat-123",
        base_currency="KRW",
        target_currency="USD",
        target_rate=1300.0,
        condition="above",
        rate_type="TTS",
        is_active=True,
    )
    mock_alert_repository.list_alerts.return_value = [active_alert]
    
    exchange_rates = [
        ExchangeRate(
            cur_unit="USD",
            cur_nm="US Dollar",
            ttb=1290.0,
            tts=1350.0,
            deal_bas_r=1320.0,
        ),
    ]
    mock_exchange_rate_client.fetch_rates.return_value = exchange_rates
    
    # Mock EventBridge error
    mock_eventbridge.put_events.side_effect = Exception("EventBridge error")
    
    with patch('functions.fetch_rates.get_alert_repository', return_value=mock_alert_repository):
        response = await fetch_rates_async()
    
    # Assertions
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Failed to fetch rates" in body["error"]
