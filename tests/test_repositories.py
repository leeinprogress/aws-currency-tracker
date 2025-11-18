
import pytest
import uuid
from app.db.models.alert import Alert
from app.db.repositories.alert_repository import DynamoDBAlertRepository

# Mark all tests in this file as asyncio
pytestmark = pytest.mark.asyncio

@pytest.fixture
def alert_repository(alerts_table):
    """Fixture to create a repository instance for each test."""
    # The alerts_table fixture ensures the mock table is created and the
    # environment variable is set before this repository is instantiated.
    return DynamoDBAlertRepository(table_name=alerts_table)

@pytest.fixture
def sample_alert_data():
    """Fixture to provide sample alert data for tests."""
    return {
        "alert_id": str(uuid.uuid4()),
        "user_id": "test-user-123",
        "telegram_chat_id": "chat-id-456",
        "base_currency": "KRW",
        "target_currency": "USD",
        "target_rate": 1300.0,
        "condition": "below",
        "rate_type": "TTS",
        "is_active": True,
    }

async def test_create_and_get_alert(alert_repository: DynamoDBAlertRepository, sample_alert_data):
    """Test creating an alert and then retrieving it."""
    # Create an alert object
    alert_to_create = Alert(**sample_alert_data)

    # Create the alert in the database
    created_alert = await alert_repository.create_alert(alert_to_create)
    assert created_alert.alert_id == sample_alert_data["alert_id"]

    # Retrieve the alert from the database
    retrieved_alert = await alert_repository.get_alert(alert_id=sample_alert_data["alert_id"])

    # Assertions
    assert retrieved_alert is not None
    assert retrieved_alert.alert_id == sample_alert_data["alert_id"]
    assert retrieved_alert.user_id == sample_alert_data["user_id"]
    assert retrieved_alert.target_currency == "USD"
    assert retrieved_alert.created_at is not None
    assert retrieved_alert.updated_at is not None

async def test_list_alerts_by_user(alert_repository: DynamoDBAlertRepository, sample_alert_data):
    """Test listing alerts for a specific user."""
    # Create a couple of alerts for the same user
    alert1 = Alert(**sample_alert_data)
    alert2_data = sample_alert_data.copy()
    alert2_data["alert_id"] = str(uuid.uuid4())
    alert2_data["target_currency"] = "EUR"
    alert2 = Alert(**alert2_data)

    await alert_repository.create_alert(alert1)
    await alert_repository.create_alert(alert2)

    # List alerts for the user
    user_alerts = await alert_repository.list_alerts(user_id=sample_alert_data["user_id"])

    # Assertions
    assert len(user_alerts) == 2
    alert_ids = {alert.alert_id for alert in user_alerts}
    assert alert1.alert_id in alert_ids
    assert alert2.alert_id in alert_ids

async def test_update_alert(alert_repository: DynamoDBAlertRepository, sample_alert_data):
    """Test updating an alert's attributes."""
    # Create an initial alert
    alert = Alert(**sample_alert_data)
    await alert_repository.create_alert(alert)

    # Update the alert's target rate and condition
    updated_alert = await alert_repository.update_alert(
        alert_id=alert.alert_id,
        target_rate=1350.5,
        is_active=False
    )

    # Assertions
    assert updated_alert is not None
    assert updated_alert.target_rate == 1350.5
    assert updated_alert.is_active is False
    assert updated_alert.updated_at > updated_alert.created_at

async def test_delete_alert(alert_repository: DynamoDBAlertRepository, sample_alert_data):
    """Test deleting an alert."""
    # Create an alert
    alert = Alert(**sample_alert_data)
    await alert_repository.create_alert(alert)

    # Ensure it exists
    retrieved_before_delete = await alert_repository.get_alert(alert.alert_id)
    assert retrieved_before_delete is not None

    # Delete the alert
    delete_result = await alert_repository.delete_alert(alert.alert_id)
    assert delete_result is True

    # Ensure it's gone
    retrieved_after_delete = await alert_repository.get_alert(alert.alert_id)
    assert retrieved_after_delete is None

async def test_get_active_alerts_by_base_currency(alert_repository: DynamoDBAlertRepository, sample_alert_data):
    """Test querying active alerts by the base currency."""
    # Create an active alert
    active_alert = Alert(**sample_alert_data)
    await alert_repository.create_alert(active_alert)

    # Create an inactive alert
    inactive_alert_data = sample_alert_data.copy()
    inactive_alert_data["alert_id"] = str(uuid.uuid4())
    inactive_alert_data["is_active"] = False
    inactive_alert = Alert(**inactive_alert_data)
    await alert_repository.create_alert(inactive_alert)

    # Query for active alerts
    active_alerts = await alert_repository.get_active_alerts_by_base_currency("KRW")

    # Assertions
    assert len(active_alerts) == 1
    assert active_alerts[0].alert_id == active_alert.alert_id
    assert active_alerts[0].is_active is True
