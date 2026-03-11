"""Tests for scoring/signals.py."""
import pytest

from app.services.scoring.features import ScoringFeatures
from app.services.scoring.signals import risk_score, trend_score, value_score


def _make_features(**kwargs) -> ScoringFeatures:
    defaults = dict(
        currency="USD",
        spot_rate=1300.0,
        buy_rate=1295.0,
        sell_rate=1305.0,
        percentile=50.0,
        z_score=0.0,
        ma7=1300.0,
        ma30=1300.0,
        ma90=1300.0,
        ma_slope=0.0,
        volatility_7d=5.0,
        volatility_30d=5.0,
        vol_ratio=1.0,
        spread_current=10.0,
        spread_avg_90d=10.0,
        spread_ratio=1.0,
        data_warning=None,
    )
    defaults.update(kwargs)
    return ScoringFeatures(**defaults)


# ---------------------------------------------------------------------------
# value_score
# ---------------------------------------------------------------------------

def test_value_score_equals_percentile():
    f = _make_features(percentile=72.0)
    assert value_score(f) == pytest.approx(72.0)


def test_value_score_clamped_above_100():
    f = _make_features(percentile=105.0)
    assert value_score(f) == 100.0


def test_value_score_clamped_below_0():
    f = _make_features(percentile=-5.0)
    assert value_score(f) == 0.0


def test_value_score_zero_percentile():
    f = _make_features(percentile=0.0)
    assert value_score(f) == 0.0


def test_value_score_100_percentile():
    f = _make_features(percentile=100.0)
    assert value_score(f) == 100.0


# ---------------------------------------------------------------------------
# trend_score
# ---------------------------------------------------------------------------

def test_trend_score_in_range():
    f = _make_features()
    score = trend_score(f)
    assert 0.0 <= score <= 100.0


def test_trend_score_neutral_conditions():
    # ma_slope=0, spot==ma30 → should be close to 50
    f = _make_features(ma_slope=0.0, spot_rate=1300.0, ma30=1300.0, volatility_30d=5.0)
    score = trend_score(f)
    assert score == pytest.approx(50.0, abs=5.0)


def test_trend_score_higher_when_falling_and_below_ma30():
    f_falling = _make_features(ma_slope=-2.0, spot_rate=1290.0, ma30=1300.0, volatility_30d=5.0)
    f_neutral = _make_features(ma_slope=0.0, spot_rate=1300.0, ma30=1300.0, volatility_30d=5.0)
    assert trend_score(f_falling) > trend_score(f_neutral)


def test_trend_score_lower_when_rising_and_above_ma30():
    f_rising = _make_features(ma_slope=2.0, spot_rate=1310.0, ma30=1300.0, volatility_30d=5.0)
    f_neutral = _make_features(ma_slope=0.0, spot_rate=1300.0, ma30=1300.0, volatility_30d=5.0)
    assert trend_score(f_rising) < trend_score(f_neutral)


# ---------------------------------------------------------------------------
# risk_score
# ---------------------------------------------------------------------------

def test_risk_score_normal_vol_no_spread():
    # vol_ratio=1.0 → vol_component=40; spread_ratio=1.0 → spread_component=0 → risk=20
    f = _make_features(vol_ratio=1.0, spread_ratio=1.0)
    assert risk_score(f) == pytest.approx(20.0)


def test_risk_score_capped_at_100():
    f = _make_features(vol_ratio=10.0, spread_ratio=10.0)
    assert risk_score(f) == 100.0


def test_risk_score_no_spread_excess():
    f = _make_features(vol_ratio=1.0, spread_ratio=0.8)
    # spread < 1 → spread_component=0; vol_component=40 → risk=20
    assert risk_score(f) == pytest.approx(20.0)


def test_risk_score_increases_with_vol_ratio():
    f_low = _make_features(vol_ratio=1.0, spread_ratio=1.0)
    f_high = _make_features(vol_ratio=2.0, spread_ratio=1.0)
    assert risk_score(f_high) > risk_score(f_low)


def test_risk_score_increases_with_spread_ratio():
    f_low = _make_features(vol_ratio=1.0, spread_ratio=1.0)
    f_high = _make_features(vol_ratio=1.0, spread_ratio=1.5)
    assert risk_score(f_high) > risk_score(f_low)
