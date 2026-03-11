"""Tests for scoring/scorer.py."""
import pytest

from app.services.scoring.guardrails import GuardrailResult
from app.services.scoring.scorer import compute_confidence, compute_final_score, compute_label


def _guardrail(name: str, triggered: bool, action: str) -> GuardrailResult:
    return GuardrailResult(name=name, triggered=triggered, action=action, explanation="")


NO_GUARDRAILS: list[GuardrailResult] = []


# ---------------------------------------------------------------------------
# compute_final_score
# ---------------------------------------------------------------------------

def test_score_normalized_mid_range():
    # raw = 0.5*50 + 0.3*50 - 0.4*0 = 40 → normalized = (40+40)/120*100 = 66.67
    score = compute_final_score(value=50.0, trend=50.0, risk=0.0, guardrails=NO_GUARDRAILS)
    assert score == pytest.approx((40 + 40) / 120 * 100, abs=0.01)


def test_score_maximum_raw():
    # raw = 0.5*100 + 0.3*100 - 0.4*0 = 80 → normalized = (80+40)/120*100 = 100
    score = compute_final_score(value=100.0, trend=100.0, risk=0.0, guardrails=NO_GUARDRAILS)
    assert score == pytest.approx(100.0)


def test_score_minimum_raw():
    # raw = 0.5*0 + 0.3*0 - 0.4*100 = -40 → normalized = (-40+40)/120*100 = 0
    score = compute_final_score(value=0.0, trend=0.0, risk=100.0, guardrails=NO_GUARDRAILS)
    assert score == pytest.approx(0.0)


def test_spread_penalty_reduces_score():
    spread_guardrail = _guardrail("wide_spread", triggered=True, action="spread_penalty")
    score_no_penalty = compute_final_score(50.0, 50.0, 0.0, NO_GUARDRAILS)
    score_with_penalty = compute_final_score(50.0, 50.0, 0.0, [spread_guardrail])
    assert score_with_penalty < score_no_penalty


def test_spread_penalty_amount():
    # raw without = 40; raw with = 25; normalized: (25+40)/120*100 = 54.17
    spread_guardrail = _guardrail("wide_spread", triggered=True, action="spread_penalty")
    score = compute_final_score(50.0, 50.0, 0.0, [spread_guardrail])
    expected = (25 + 40) / 120 * 100
    assert score == pytest.approx(expected, abs=0.01)


def test_untriggered_guardrail_no_effect():
    untriggered = _guardrail("wide_spread", triggered=False, action="spread_penalty")
    score_no = compute_final_score(50.0, 50.0, 0.0, NO_GUARDRAILS)
    score_with = compute_final_score(50.0, 50.0, 0.0, [untriggered])
    assert score_no == pytest.approx(score_with)


def test_score_clamped_at_100():
    # Ensure result never exceeds 100 even with extreme inputs
    score = compute_final_score(100.0, 100.0, 0.0, NO_GUARDRAILS)
    assert score <= 100.0


def test_score_clamped_at_0():
    spread = _guardrail("wide_spread", triggered=True, action="spread_penalty")
    score = compute_final_score(0.0, 0.0, 100.0, [spread])
    assert score >= 0.0


# ---------------------------------------------------------------------------
# compute_label
# ---------------------------------------------------------------------------

def test_label_favorable_at_70():
    assert compute_label(70.0, NO_GUARDRAILS) == "FAVORABLE"


def test_label_favorable_above_70():
    assert compute_label(85.0, NO_GUARDRAILS) == "FAVORABLE"


def test_label_neutral_at_40():
    assert compute_label(40.0, NO_GUARDRAILS) == "NEUTRAL"


def test_label_neutral_between_40_and_70():
    assert compute_label(55.0, NO_GUARDRAILS) == "NEUTRAL"


def test_label_wait_below_40():
    assert compute_label(39.9, NO_GUARDRAILS) == "WAIT"


def test_label_wait_at_zero():
    assert compute_label(0.0, NO_GUARDRAILS) == "WAIT"


def test_force_caution_overrides_favorable():
    caution = _guardrail("high_risk", triggered=True, action="force_caution")
    assert compute_label(90.0, [caution]) == "CAUTION"


def test_force_caution_overrides_wait():
    caution = _guardrail("high_risk", triggered=True, action="force_caution")
    assert compute_label(10.0, [caution]) == "CAUTION"


def test_downgrade_label_favorable_to_neutral():
    dg = _guardrail("high_volatility", triggered=True, action="downgrade_label")
    assert compute_label(80.0, [dg]) == "NEUTRAL"


def test_downgrade_label_neutral_to_wait():
    dg = _guardrail("high_volatility", triggered=True, action="downgrade_label")
    assert compute_label(55.0, [dg]) == "WAIT"


def test_downgrade_label_wait_stays_wait():
    dg = _guardrail("high_volatility", triggered=True, action="downgrade_label")
    assert compute_label(20.0, [dg]) == "WAIT"


def test_force_caution_takes_priority_over_downgrade():
    dg = _guardrail("high_volatility", triggered=True, action="downgrade_label")
    caution = _guardrail("high_risk", triggered=True, action="force_caution")
    assert compute_label(80.0, [dg, caution]) == "CAUTION"


def test_untriggered_downgrade_no_effect():
    dg = _guardrail("high_volatility", triggered=False, action="downgrade_label")
    assert compute_label(80.0, [dg]) == "FAVORABLE"


# ---------------------------------------------------------------------------
# compute_confidence
# ---------------------------------------------------------------------------

def test_confidence_high_below_30():
    assert compute_confidence(29.9) == "HIGH"


def test_confidence_medium_at_30():
    assert compute_confidence(30.0) == "MEDIUM"


def test_confidence_medium_between_30_and_60():
    assert compute_confidence(50.0) == "MEDIUM"


def test_confidence_low_at_60():
    assert compute_confidence(60.0) == "LOW"


def test_confidence_low_above_60():
    assert compute_confidence(90.0) == "LOW"


def test_confidence_low_when_data_warning_present():
    # data_warning forces LOW regardless of risk
    assert compute_confidence(10.0, data_warning="Less than 30 days of history") == "LOW"


def test_confidence_not_overridden_when_no_data_warning():
    assert compute_confidence(10.0, data_warning=None) == "HIGH"
