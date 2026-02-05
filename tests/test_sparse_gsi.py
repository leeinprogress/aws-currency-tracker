"""
Tests for sparse GSI pattern on AlertsTable.

The active_user_id-index is a sparse index that only contains active alerts.
This enables efficient queries without scanning inactive alerts.
"""
import pytest
import uuid

from app.domain.entities.alert import Alert
from app.infrastructure.persistence.dynamodb_alert_repository import DynamoDBAlertRepository

pytestmark = pytest.mark.asyncio


@pytest.fixture
def alert_repo(alerts_table):
    return DynamoDBAlertRepository(table_name=alerts_table)


def create_alert(user_id: str, is_active: bool = True, currency: str = "USD") -> Alert:
    return Alert(
        alert_id=str(uuid.uuid4()),
        user_id=user_id,
        telegram_chat_id="123456789",
        target_currency=currency,
        target_rate=1350.0,
        condition="above",
        rate_type="TTS",
        is_active=is_active,
    )


async def test_sparse_gsi_only_indexes_active_alerts(alert_repo):
    """Active alerts should be queryable via sparse GSI."""
    user_id = "test-user-sparse"

    # Create active and inactive alerts
    active_alert = create_alert(user_id, is_active=True)
    inactive_alert = create_alert(user_id, is_active=False)

    await alert_repo.save(active_alert)
    await alert_repo.save(inactive_alert)

    # Query active alerts via sparse GSI
    active_alerts = await alert_repo.find_by_user(user_id, is_active=True)
    assert len(active_alerts) == 1
    assert active_alerts[0].alert_id == active_alert.alert_id

    # Query inactive alerts (uses filter on user_id-index)
    inactive_alerts = await alert_repo.find_by_user(user_id, is_active=False)
    assert len(inactive_alerts) == 1
    assert inactive_alerts[0].alert_id == inactive_alert.alert_id

    # Query all alerts (no filter)
    all_alerts = await alert_repo.find_by_user(user_id)
    assert len(all_alerts) == 2


async def test_deactivating_alert_removes_from_sparse_index(alert_repo):
    """When an alert is deactivated, it should be removed from sparse GSI."""
    user_id = "test-user-deactivate"

    alert = create_alert(user_id, is_active=True)
    await alert_repo.save(alert)

    # Verify it's in sparse index
    active_alerts = await alert_repo.find_by_user(user_id, is_active=True)
    assert len(active_alerts) == 1

    # Deactivate the alert
    await alert_repo.update(alert.alert_id, is_active=False)

    # Should no longer appear in active query
    active_alerts = await alert_repo.find_by_user(user_id, is_active=True)
    assert len(active_alerts) == 0

    # Should appear in inactive query
    inactive_alerts = await alert_repo.find_by_user(user_id, is_active=False)
    assert len(inactive_alerts) == 1


async def test_reactivating_alert_adds_to_sparse_index(alert_repo):
    """When an alert is reactivated, it should be added back to sparse GSI."""
    user_id = "test-user-reactivate"

    # Create inactive alert
    alert = create_alert(user_id, is_active=False)
    await alert_repo.save(alert)

    # Verify not in sparse index
    active_alerts = await alert_repo.find_by_user(user_id, is_active=True)
    assert len(active_alerts) == 0

    # Reactivate the alert
    await alert_repo.update(alert.alert_id, is_active=True)

    # Should now appear in active query
    active_alerts = await alert_repo.find_by_user(user_id, is_active=True)
    assert len(active_alerts) == 1
    assert active_alerts[0].alert_id == alert.alert_id


async def test_multiple_users_sparse_gsi_isolation(alert_repo):
    """Each user's active alerts are isolated in sparse GSI queries."""
    user_1 = "user-1"
    user_2 = "user-2"

    # Create alerts for both users
    await alert_repo.save(create_alert(user_1, is_active=True, currency="USD"))
    await alert_repo.save(create_alert(user_1, is_active=True, currency="EUR"))
    await alert_repo.save(create_alert(user_1, is_active=False, currency="JPY"))
    await alert_repo.save(create_alert(user_2, is_active=True, currency="USD"))

    # Query user_1's active alerts
    user_1_active = await alert_repo.find_by_user(user_1, is_active=True)
    assert len(user_1_active) == 2

    # Query user_2's active alerts
    user_2_active = await alert_repo.find_by_user(user_2, is_active=True)
    assert len(user_2_active) == 1

    # Query user_1's all alerts
    user_1_all = await alert_repo.find_by_user(user_1)
    assert len(user_1_all) == 3
