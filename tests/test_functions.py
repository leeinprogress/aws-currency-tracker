import json
import pytest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

from app.domain.entities.alert import Alert
from app.clients.exchange_rate_client import ExchangeRate
from functions.check_alerts import check_alerts_async
from functions.fetch_rates import fetch_rates_async

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_telegram_bot():
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.close = AsyncMock()
    with patch('functions.check_alerts.get_telegram_bot', return_value=mock_bot):
        yield mock_bot


async def test_check_alerts_handler_triggers_one_alert(alerts_table, mock_telegram_bot):
    user_id = "test-user-lambda"
    chat_id = "test-chat-lambda"
    
    alert_to_trigger = Alert(
        alert_id=str(uuid.uuid4()),
        user_id=user_id,
        telegram_chat_id=chat_id,
        target_currency="USD",
        target_rate=1300.0,
        condition="above",
        rate_type="TTS",
        is_active=True,
    )
    
    alert_not_triggered = Alert(
        alert_id=str(uuid.uuid4()),
        user_id=user_id,
        telegram_chat_id=chat_id,
        target_currency="USD",
        target_rate=1400.0,
        condition="above",
        rate_type="TTS",
        is_active=True,
    )
    
    inactive_alert = Alert(
        alert_id=str(uuid.uuid4()),
        user_id=user_id,
        telegram_chat_id=chat_id,
        target_currency="USD",
        target_rate=1200.0,
        condition="above",
        rate_type="TTS",
        is_active=False,
    )

    import boto3
    from app.infrastructure.persistence.mappers import AlertMapper
    from datetime import datetime, UTC
    
    mapper = AlertMapper()
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(alerts_table)
    
    item1 = mapper.to_dynamodb(alert_to_trigger)
    item1["created_at"] = datetime.now(UTC).isoformat()
    item1["updated_at"] = datetime.now(UTC).isoformat()
    table.put_item(Item=item1)
    
    item2 = mapper.to_dynamodb(alert_not_triggered)
    item2["created_at"] = datetime.now(UTC).isoformat()
    item2["updated_at"] = datetime.now(UTC).isoformat()
    table.put_item(Item=item2)
    
    item3 = mapper.to_dynamodb(inactive_alert)
    item3["created_at"] = datetime.now(UTC).isoformat()
    item3["updated_at"] = datetime.now(UTC).isoformat()
    table.put_item(Item=item3)

    event = {
        "source": "currency.tracker",
        "detail-type": "Rate Updated",
        "detail": json.dumps({
            "base_currency": "KRW",
            "rates": {
                "USD": {
                    "TTS": "1350.50",
                    "TTB": "1290.00",
                    "cur_nm": "US Dollar"
                }
            },
            "timestamp": "2025-11-18T12:00:00Z"
        })
    }

    response = await check_alerts_async(event)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "Checked 2 alerts"
    assert body["target_triggered"] == 1
    assert body["triggered_alert_ids"][0] == alert_to_trigger.alert_id

    mock_telegram_bot.send_message.assert_called_once()
    
    call_args = mock_telegram_bot.send_message.call_args
    assert call_args.kwargs['chat_id'] == chat_id
    assert "Target Rate Reached!" in call_args.kwargs['text']
    assert "1,300.00" in call_args.kwargs['text']
    assert "1,350.50" in call_args.kwargs['text']


@pytest.fixture
def mock_alert_repository():
    mock_repo = MagicMock()
    mock_repo.list_alerts = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_exchange_rate_client():
    with patch('functions.fetch_rates.KoreaEximExchangeRateClient') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_eventbridge():
    with patch('functions.fetch_rates.boto3.client') as mock_client:
        mock_eb = MagicMock()
        mock_client.return_value = mock_eb
        yield mock_eb


@pytest.fixture
def mock_rate_history_repo():
    with patch('functions.fetch_rates.DynamoDBRateHistoryRepository') as mock_repo_class:
        mock_repo = AsyncMock()
        mock_repo.save_batch = AsyncMock(return_value=1)
        mock_repo_class.return_value = mock_repo
        yield mock_repo


async def test_fetch_rates_no_active_alerts(
    mock_alert_repository,
    mock_exchange_rate_client,
    mock_eventbridge,
    mock_rate_history_repo,
):
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
    
    response = await fetch_rates_async()
    
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "Fetched rates for 1 currencies"
    
    mock_exchange_rate_client.fetch_rates.assert_called()
    mock_eventbridge.put_events.assert_called_once()


async def test_fetch_rates_no_exchange_rates(
    mock_alert_repository,
    mock_exchange_rate_client,
    mock_eventbridge,
):
    mock_exchange_rate_client.fetch_rates.return_value = []
    
    response = await fetch_rates_async()
    
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "No exchange rates available"
    
    mock_exchange_rate_client.fetch_rates.assert_called()
    mock_eventbridge.put_events.assert_not_called()


async def test_fetch_rates_success(
    mock_alert_repository,
    mock_exchange_rate_client,
    mock_eventbridge,
    mock_rate_history_repo,
):
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
    
    response = await fetch_rates_async()
    
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "Fetched rates for 2 currencies"
    assert set(body["currencies"]) == {"USD", "EUR"}
    
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
    mock_exchange_rate_client.fetch_rates.side_effect = Exception("API connection failed")
    
    response = await fetch_rates_async()
    
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Failed to fetch rates" in body["error"]
    assert "API connection failed" in body["error"]
    
    mock_eventbridge.put_events.assert_not_called()


async def test_fetch_rates_eventbridge_error(
    mock_alert_repository,
    mock_exchange_rate_client,
    mock_eventbridge,
):
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
    
    mock_eventbridge.put_events.side_effect = Exception("EventBridge error")
    
    response = await fetch_rates_async()
    
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Failed to fetch rates" in body["error"]
