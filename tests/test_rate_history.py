import pytest
from datetime import datetime, timedelta, UTC

from app.domain.entities.rate_history import RateHistory
from app.infrastructure.persistence.dynamodb_rate_history_repository import DynamoDBRateHistoryRepository

pytestmark = pytest.mark.asyncio


@pytest.fixture
def rate_history_repo(rate_history_table):
    return DynamoDBRateHistoryRepository(table_name=rate_history_table)


@pytest.fixture
def sample_rate_history():
    now = datetime.now(UTC)
    return RateHistory(
        currency_code="USD",
        timestamp=now,
        currency_name="US Dollar",
        ttb=1290.0,
        tts=1350.0,
        deal_bas_r=1320.0,
        source_date="20240201",
        created_at=now,
    )


async def test_save_and_find_latest(rate_history_repo, sample_rate_history):
    # Save a rate history record
    saved = await rate_history_repo.save(sample_rate_history)
    assert saved.currency_code == "USD"

    # Find the latest
    latest = await rate_history_repo.find_latest("USD")
    assert latest is not None
    assert latest.currency_code == "USD"
    assert latest.tts == 1350.0
    assert latest.source_date == "20240201"


async def test_save_batch(rate_history_repo):
    now = datetime.now(UTC)
    rates = [
        RateHistory(
            currency_code="USD",
            timestamp=now,
            currency_name="US Dollar",
            ttb=1290.0,
            tts=1350.0,
            deal_bas_r=1320.0,
            source_date="20240201",
        ),
        RateHistory(
            currency_code="EUR",
            timestamp=now,
            currency_name="Euro",
            ttb=1400.0,
            tts=1450.0,
            deal_bas_r=1425.0,
            source_date="20240201",
        ),
        RateHistory(
            currency_code="JPY",
            timestamp=now,
            currency_name="Japanese Yen",
            ttb=8.5,
            tts=9.0,
            deal_bas_r=8.75,
            source_date="20240201",
        ),
    ]

    saved_count = await rate_history_repo.save_batch(rates)
    assert saved_count == 3

    # Verify all were saved
    usd_latest = await rate_history_repo.find_latest("USD")
    eur_latest = await rate_history_repo.find_latest("EUR")
    jpy_latest = await rate_history_repo.find_latest("JPY")

    assert usd_latest is not None
    assert eur_latest is not None
    assert jpy_latest is not None


async def test_find_by_currency_range(rate_history_repo):
    now = datetime.now(UTC)

    # Save multiple records at different times
    for i in range(5):
        rate = RateHistory(
            currency_code="USD",
            timestamp=now - timedelta(hours=i),
            currency_name="US Dollar",
            ttb=1290.0 + i,
            tts=1350.0 + i,
            deal_bas_r=1320.0 + i,
            source_date=f"2024020{i+1}",
        )
        await rate_history_repo.save(rate)

    # Query for the last 3 hours
    start_date = now - timedelta(hours=3)
    end_date = now + timedelta(hours=1)

    history = await rate_history_repo.find_by_currency_range(
        currency_code="USD",
        start_date=start_date,
        end_date=end_date,
        limit=10,
    )

    # Should get 4 records (0, 1, 2, 3 hours ago)
    assert len(history) == 4

    # Should be sorted newest first
    assert history[0].timestamp > history[-1].timestamp


async def test_find_by_currency_range_with_limit(rate_history_repo):
    now = datetime.now(UTC)

    # Save 10 records
    for i in range(10):
        rate = RateHistory(
            currency_code="EUR",
            timestamp=now - timedelta(hours=i),
            currency_name="Euro",
            ttb=1400.0 + i,
            tts=1450.0 + i,
            deal_bas_r=1425.0 + i,
            source_date=f"2024020{i}",
        )
        await rate_history_repo.save(rate)

    # Query with limit
    history = await rate_history_repo.find_by_currency_range(
        currency_code="EUR",
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(hours=1),
        limit=5,
    )

    assert len(history) == 5


async def test_find_latest_not_found(rate_history_repo):
    latest = await rate_history_repo.find_latest("NONEXISTENT")
    assert latest is None


async def test_rate_history_calculate_change():
    now = datetime.now(UTC)

    current = RateHistory(
        currency_code="USD",
        timestamp=now,
        currency_name="US Dollar",
        ttb=1300.0,
        tts=1350.0,
        deal_bas_r=1320.0,
        source_date="20240202",
    )

    previous = RateHistory(
        currency_code="USD",
        timestamp=now - timedelta(hours=6),
        currency_name="US Dollar",
        ttb=1290.0,
        tts=1340.0,
        deal_bas_r=1300.0,
        source_date="20240201",
    )

    # Calculate change using DEAL_BAS_R (default)
    change = current.calculate_change(previous)
    assert change is not None
    assert abs(change - 1.538) < 0.01  # (1320 - 1300) / 1300 * 100 ≈ 1.538%

    # Calculate change using TTS
    change_tts = current.calculate_change(previous, rate_type="TTS")
    assert change_tts is not None
    assert abs(change_tts - 0.746) < 0.01  # (1350 - 1340) / 1340 * 100 ≈ 0.746%


async def test_rate_history_get_rate_by_type():
    rate = RateHistory(
        currency_code="USD",
        timestamp=datetime.now(UTC),
        currency_name="US Dollar",
        ttb=1290.0,
        tts=1350.0,
        deal_bas_r=1320.0,
        source_date="20240201",
    )

    assert rate.get_rate_by_type("TTS") == 1350.0
    assert rate.get_rate_by_type("TTB") == 1290.0
    assert rate.get_rate_by_type("DEAL_BAS_R") == 1320.0
    assert rate.get_rate_by_type("UNKNOWN") == 1320.0  # Falls back to deal_bas_r
