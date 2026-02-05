import pytest
import uuid

from app.domain.entities.alert import Alert
from app.infrastructure.persistence.dynamodb_alert_repository import (
    DynamoDBAlertRepository,
    DuplicateAlertError,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def alert_repo(alerts_table):
    return DynamoDBAlertRepository(table_name=alerts_table)


@pytest.fixture
def sample_alert():
    return Alert(
        alert_id=str(uuid.uuid4()),
        user_id="test-user-1",
        telegram_chat_id="123456789",
        target_currency="USD",
        target_rate=1350.0,
        condition="above",
        rate_type="TTS",
        is_active=True,
    )


async def test_save_with_duplicate_check_success(alert_repo, sample_alert):
    # First save should succeed
    saved = await alert_repo.save(sample_alert, check_duplicate=True)
    assert saved.alert_id == sample_alert.alert_id


async def test_save_with_duplicate_check_fails_on_duplicate(alert_repo, sample_alert):
    # First save succeeds
    await alert_repo.save(sample_alert, check_duplicate=True)

    # Second save with same ID should fail
    with pytest.raises(DuplicateAlertError) as exc_info:
        await alert_repo.save(sample_alert, check_duplicate=True)

    assert sample_alert.alert_id in str(exc_info.value)


async def test_save_without_duplicate_check_overwrites(alert_repo, sample_alert):
    # First save
    await alert_repo.save(sample_alert, check_duplicate=True)

    # Modify the alert
    sample_alert.target_rate = 1400.0

    # Save without duplicate check should overwrite
    await alert_repo.save(sample_alert, check_duplicate=False)

    # Verify it was overwritten
    fetched = await alert_repo.find_by_id(sample_alert.alert_id)
    assert fetched.target_rate == 1400.0


async def test_update_alert(alert_repo, sample_alert):
    # Save the alert
    await alert_repo.save(sample_alert)

    # Update without expected_updated_at (no optimistic locking)
    updated = await alert_repo.update(
        alert_id=sample_alert.alert_id,
        target_rate=1400.0,
    )

    assert updated is not None
    assert updated.target_rate == 1400.0


async def test_find_duplicate_alert_found(alert_repo, sample_alert):
    # Save the alert
    await alert_repo.save(sample_alert)

    # Find duplicate with same parameters
    duplicate = await alert_repo.find_duplicate(
        user_id=sample_alert.user_id,
        target_currency=sample_alert.target_currency,
        condition=sample_alert.condition,
        rate_type=sample_alert.rate_type,
    )

    assert duplicate is not None
    assert duplicate.alert_id == sample_alert.alert_id


async def test_find_duplicate_alert_not_found_different_currency(alert_repo, sample_alert):
    # Save the alert
    await alert_repo.save(sample_alert)

    # Find with different currency
    duplicate = await alert_repo.find_duplicate(
        user_id=sample_alert.user_id,
        target_currency="EUR",
        condition=sample_alert.condition,
        rate_type=sample_alert.rate_type,
    )

    assert duplicate is None


async def test_find_duplicate_alert_not_found_different_user(alert_repo, sample_alert):
    # Save the alert
    await alert_repo.save(sample_alert)

    # Find with different user
    duplicate = await alert_repo.find_duplicate(
        user_id="different-user",
        target_currency=sample_alert.target_currency,
        condition=sample_alert.condition,
        rate_type=sample_alert.rate_type,
    )

    assert duplicate is None


async def test_find_duplicate_ignores_inactive_alerts(alert_repo, sample_alert):
    # Save an inactive alert
    sample_alert.is_active = False
    await alert_repo.save(sample_alert)

    # Find duplicate should not find inactive alerts
    duplicate = await alert_repo.find_duplicate(
        user_id=sample_alert.user_id,
        target_currency=sample_alert.target_currency,
        condition=sample_alert.condition,
        rate_type=sample_alert.rate_type,
    )

    assert duplicate is None
