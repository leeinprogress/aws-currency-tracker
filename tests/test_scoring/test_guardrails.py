"""Tests for scoring/guardrails.py."""

from app.services.scoring.features import ScoringFeatures
from app.services.scoring.guardrails import apply_guardrails


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
# Rule 1: high_volatility (vol_ratio > 1.5 → downgrade_label)
# ---------------------------------------------------------------------------

def test_high_volatility_triggered_above_threshold():
    f = _make_features(vol_ratio=1.6)
    results = apply_guardrails(f, risk=20.0)
    hv = next(g for g in results if g.name == "high_volatility")
    assert hv.triggered is True
    assert hv.action == "downgrade_label"
    assert len(hv.explanation) > 0


def test_high_volatility_not_triggered_at_threshold():
    f = _make_features(vol_ratio=1.5)
    results = apply_guardrails(f, risk=20.0)
    hv = next(g for g in results if g.name == "high_volatility")
    assert hv.triggered is False
    assert hv.explanation == ""


def test_high_volatility_not_triggered_below_threshold():
    f = _make_features(vol_ratio=1.4)
    results = apply_guardrails(f, risk=20.0)
    hv = next(g for g in results if g.name == "high_volatility")
    assert hv.triggered is False


def test_high_volatility_explanation_contains_ratio():
    f = _make_features(vol_ratio=2.0)
    results = apply_guardrails(f, risk=20.0)
    hv = next(g for g in results if g.name == "high_volatility")
    assert "2.0x" in hv.explanation


# ---------------------------------------------------------------------------
# Rule 2: wide_spread (spread_ratio > 1.35 → spread_penalty)
# ---------------------------------------------------------------------------

def test_wide_spread_triggered_above_threshold():
    f = _make_features(spread_ratio=1.4)
    results = apply_guardrails(f, risk=20.0)
    ws = next(g for g in results if g.name == "wide_spread")
    assert ws.triggered is True
    assert ws.action == "spread_penalty"
    assert len(ws.explanation) > 0


def test_wide_spread_not_triggered_at_threshold():
    f = _make_features(spread_ratio=1.35)
    results = apply_guardrails(f, risk=20.0)
    ws = next(g for g in results if g.name == "wide_spread")
    assert ws.triggered is False


def test_wide_spread_not_triggered_below_threshold():
    f = _make_features(spread_ratio=1.2)
    results = apply_guardrails(f, risk=20.0)
    ws = next(g for g in results if g.name == "wide_spread")
    assert ws.triggered is False


def test_wide_spread_explanation_contains_percentage():
    f = _make_features(spread_ratio=1.5)  # 50% wider
    results = apply_guardrails(f, risk=20.0)
    ws = next(g for g in results if g.name == "wide_spread")
    assert "50%" in ws.explanation


# ---------------------------------------------------------------------------
# Rule 3: high_risk (risk > 80 → force_caution)
# ---------------------------------------------------------------------------

def test_high_risk_triggered_above_threshold():
    f = _make_features()
    results = apply_guardrails(f, risk=81.0)
    hr = next(g for g in results if g.name == "high_risk")
    assert hr.triggered is True
    assert hr.action == "force_caution"
    assert len(hr.explanation) > 0


def test_high_risk_not_triggered_at_threshold():
    f = _make_features()
    results = apply_guardrails(f, risk=80.0)
    hr = next(g for g in results if g.name == "high_risk")
    assert hr.triggered is False


def test_high_risk_not_triggered_below_threshold():
    f = _make_features()
    results = apply_guardrails(f, risk=79.0)
    hr = next(g for g in results if g.name == "high_risk")
    assert hr.triggered is False


# ---------------------------------------------------------------------------
# All 3 simultaneously
# ---------------------------------------------------------------------------

def test_all_three_guardrails_simultaneously():
    f = _make_features(vol_ratio=2.0, spread_ratio=1.5)
    results = apply_guardrails(f, risk=90.0)
    assert len(results) == 3
    assert all(g.triggered for g in results)


def test_no_guardrails_triggered():
    f = _make_features(vol_ratio=1.0, spread_ratio=1.0)
    results = apply_guardrails(f, risk=20.0)
    assert all(not g.triggered for g in results)


def test_always_returns_three_results():
    f = _make_features()
    results = apply_guardrails(f, risk=0.0)
    assert len(results) == 3
