import pytest
import uuid
from app.domain.entities.alert import Alert
from app.infrastructure.persistence.dynamodb_alert_repository import DynamoDBAlertRepository

pytestmark = pytest.mark.asyncio


@pytest.fixture
def alert_repository(alerts_table):
    return DynamoDBAlertRepository(table_name=alerts_table)


@pytest.fixture
def sample_alert_data():
    return {
        "alert_id": str(uuid.uuid4()),
        "user_id": "test-user-123",
        "telegram_chat_id": "chat-id-456",
        "target_currency": "USD",
        "target_rate": 1300.0,
        "condition": "below",
        "rate_type": "TTS",
        "is_active": True,
    }


async def test_create_and_get_alert(alert_repository: DynamoDBAlertRepository, sample_alert_data):
    alert_to_create = Alert(**sample_alert_data)

    created_alert = await alert_repository.save(alert_to_create)
    assert created_alert.alert_id == sample_alert_data["alert_id"]

    retrieved_alert = await alert_repository.find_by_id(alert_id=sample_alert_data["alert_id"])

    assert retrieved_alert is not None
    assert retrieved_alert.alert_id == sample_alert_data["alert_id"]
    assert retrieved_alert.user_id == sample_alert_data["user_id"]
    assert retrieved_alert.target_currency == "USD"
    assert retrieved_alert.created_at is not None
    assert retrieved_alert.updated_at is not None


async def test_list_alerts_by_user(alert_repository: DynamoDBAlertRepository, sample_alert_data):
    alert1 = Alert(**sample_alert_data)
    alert2_data = sample_alert_data.copy()
    alert2_data["alert_id"] = str(uuid.uuid4())
    alert2_data["target_currency"] = "EUR"
    alert2 = Alert(**alert2_data)

    await alert_repository.save(alert1)
    await alert_repository.save(alert2)

    user_alerts = await alert_repository.find_by_user(user_id=sample_alert_data["user_id"])

    assert len(user_alerts) == 2
    alert_ids = {alert.alert_id for alert in user_alerts}
    assert alert1.alert_id in alert_ids
    assert alert2.alert_id in alert_ids


async def test_update_alert(alert_repository: DynamoDBAlertRepository, sample_alert_data):
    alert = Alert(**sample_alert_data)
    await alert_repository.save(alert)

    updated_alert = await alert_repository.update(
        alert_id=alert.alert_id,
        target_rate=1350.5,
        is_active=False
    )

    assert updated_alert is not None
    assert updated_alert.target_rate == 1350.5
    assert updated_alert.is_active is False
    assert updated_alert.updated_at > updated_alert.created_at


async def test_delete_alert(alert_repository: DynamoDBAlertRepository, sample_alert_data):
    alert = Alert(**sample_alert_data)
    await alert_repository.save(alert)

    retrieved_before_delete = await alert_repository.find_by_id(alert.alert_id)
    assert retrieved_before_delete is not None

    delete_result = await alert_repository.delete(alert.alert_id)
    assert delete_result is True

    retrieved_after_delete = await alert_repository.find_by_id(alert.alert_id)
    assert retrieved_after_delete is None


async def test_get_active_alerts_by_base_currency(alert_repository: DynamoDBAlertRepository, sample_alert_data):
    active_alert = Alert(**sample_alert_data)
    await alert_repository.save(active_alert)

    inactive_alert_data = sample_alert_data.copy()
    inactive_alert_data["alert_id"] = str(uuid.uuid4())
    inactive_alert_data["is_active"] = False
    inactive_alert = Alert(**inactive_alert_data)
    await alert_repository.save(inactive_alert)

    active_alerts = await alert_repository.find_all_active()

    assert len(active_alerts) == 1
    assert active_alerts[0].alert_id == active_alert.alert_id
    assert active_alerts[0].is_active is True
