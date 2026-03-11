"""Tests for scoring/features.py — compute_features and data guards."""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import InsufficientDataError, ScoringUnavailableError
from app.domain.entities.rate_history import RateHistory
from app.services.scoring.features import compute_features


def _make_history(
    rates: list[float],
    *,
    buy_offset: float = -5.0,
    sell_offset: float = 5.0,
    days_ago_start: int | None = None,
    stale_days: int | None = None,
) -> list[RateHistory]:
    """Create ascending RateHistory list from a list of mid rates."""
    now = datetime.now(timezone.utc)
    n = len(rates)
    records = []
    for i, rate in enumerate(rates):
        if stale_days is not None:
            ts = now - timedelta(days=stale_days + (n - 1 - i))
        else:
            offset = n - 1 - i
            ts = now - timedelta(days=offset)
        records.append(
            RateHistory(
                currency_code="USD",
                timestamp=ts,
                currency_name="US Dollar",
                ttb=rate + buy_offset,
                tts=rate + sell_offset,
                deal_bas_r=rate,
                source_date=ts.strftime("%Y%m%d"),
            )
        )
    return records


# ---------------------------------------------------------------------------
# Data guard tests
# ---------------------------------------------------------------------------

def test_empty_history_raises_scoring_unavailable():
    with pytest.raises(ScoringUnavailableError):
        compute_features("USD", [], 1300.0)


def test_less_than_7_raises_insufficient_data():
    history = _make_history([1300.0] * 6)
    with pytest.raises(InsufficientDataError) as exc_info:
        compute_features("USD", history, 1300.0)
    assert exc_info.value.min_required == 7
    assert exc_info.value.actual == 6


def test_exactly_7_records_succeeds():
    history = _make_history([1300.0] * 7)
    features = compute_features("USD", history, 1300.0)
    assert features is not None
    assert features.data_warning == "Less than 30 days of history"


def test_less_than_30_sets_data_warning():
    history = _make_history([1300.0] * 20)
    features = compute_features("USD", history, 1300.0)
    assert features.data_warning == "Less than 30 days of history"


def test_30_or_more_records_no_data_warning():
    history = _make_history([1300.0] * 30)
    features = compute_features("USD", history, 1300.0)
    assert features.data_warning is None


def test_stale_data_sets_data_warning():
    # Last record is 5 days ago → stale
    history = _make_history([1300.0] * 30, stale_days=5)
    features = compute_features("USD", history, 1300.0)
    assert features.data_warning is not None
    assert "stale" in features.data_warning.lower()


def test_stale_and_less_than_30_combines_warnings():
    history = _make_history([1300.0] * 10, stale_days=5)
    features = compute_features("USD", history, 1300.0)
    assert features.data_warning is not None
    assert "30 days" in features.data_warning
    assert "stale" in features.data_warning


def test_zero_pstdev_z_score_is_zero():
    # All rates identical → pstdev = 0 → z_score = 0
    history = _make_history([1300.0] * 30)
    features = compute_features("USD", history, 1300.0)
    assert features.z_score == 0.0


# ---------------------------------------------------------------------------
# Feature value tests (known synthetic data)
# ---------------------------------------------------------------------------

def test_percentile_all_below():
    # current_rate is higher than all history → percentile = 100%
    history = _make_history([1300.0] * 30)
    features = compute_features("USD", history, 1400.0)
    assert features.percentile == 100.0


def test_percentile_all_above():
    # current_rate is lower than all history → percentile = 0%
    history = _make_history([1300.0] * 30)
    features = compute_features("USD", history, 1200.0)
    assert features.percentile == 0.0


def test_ma7_calculation():
    # Last 7 rates are 1310–1316 (ascending)
    rates = [1300.0] * 23 + [1310.0, 1311.0, 1312.0, 1313.0, 1314.0, 1315.0, 1316.0]
    history = _make_history(rates)
    features = compute_features("USD", history, 1316.0)
    expected_ma7 = (1310 + 1311 + 1312 + 1313 + 1314 + 1315 + 1316) / 7
    assert abs(features.ma7 - expected_ma7) < 0.01


def test_ma30_calculation():
    rates = list(range(1271, 1301))  # 30 values: 1271..1300
    history = _make_history(rates)
    features = compute_features("USD", history, 1300.0)
    expected_ma30 = sum(range(1271, 1301)) / 30
    assert abs(features.ma30 - expected_ma30) < 0.01


def test_ma_slope_zero_with_fewer_than_12():
    history = _make_history([1300.0] * 10)
    features = compute_features("USD", history, 1300.0)
    assert features.ma_slope == 0.0


def test_ma_slope_nonzero_with_12_or_more():
    # Ascending rates → ma7 today > ma7_5d_ago → positive slope
    rates = list(range(1280, 1310))  # 30 values, strictly ascending
    history = _make_history(rates)
    features = compute_features("USD", history, 1310.0)
    assert features.ma_slope > 0


def test_vol_ratio_equals_one_when_30d_is_zero():
    # Identical rates → volatility_30d = 0 → vol_ratio defaults to 1.0
    history = _make_history([1300.0] * 30)
    features = compute_features("USD", history, 1300.0)
    assert features.vol_ratio == 1.0


def test_spread_current_and_avg():
    # buy = rate - 5, sell = rate + 5 → spread = 10 everywhere
    history = _make_history([1300.0] * 30, buy_offset=-5.0, sell_offset=5.0)
    features = compute_features("USD", history, 1300.0)
    assert abs(features.spread_current - 10.0) < 0.001
    assert abs(features.spread_avg_90d - 10.0) < 0.001
    assert abs(features.spread_ratio - 1.0) < 0.001


def test_spread_ratio_elevated():
    # Most history has spread 10, last record has spread 15
    rates = [1300.0] * 30
    history = _make_history(rates, buy_offset=-5.0, sell_offset=5.0)
    # Override last record's spread
    history[-1].ttb = 1295.0  # buy 5 lower
    history[-1].tts = 1310.0  # sell 10 higher → spread 15
    features = compute_features("USD", history, 1300.0)
    assert features.spread_current == pytest.approx(15.0, abs=0.01)
    assert features.spread_ratio > 1.0


def test_currency_stored_in_features():
    history = _make_history([1300.0] * 30)
    features = compute_features("JPY", history, 1300.0)
    assert features.currency == "JPY"


def test_spot_rate_stored_in_features():
    history = _make_history([1300.0] * 30)
    features = compute_features("USD", history, 1350.0)
    assert features.spot_rate == 1350.0
