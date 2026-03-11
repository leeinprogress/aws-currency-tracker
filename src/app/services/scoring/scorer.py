from typing import Optional

from app.services.scoring.guardrails import GuardrailResult


def compute_final_score(
    value: float,
    trend: float,
    risk: float,
    guardrails: list[GuardrailResult],
) -> float:
    # 1. Raw score (range: -55 to 80 with spread penalty, -40 to 80 without)
    raw = (0.5 * value) + (0.3 * trend) - (0.4 * risk)
    if any(g.triggered and g.action == "spread_penalty" for g in guardrails):
        raw -= 15

    # 2. Normalize to [0, 100]
    # Formula: (raw + 40) / 120 * 100
    # Derivation: min raw = -40, range = 120 → maps [-40, 80] → [0, 100]
    final = (raw + 40) / 120 * 100
    return max(0.0, min(100.0, final))


def compute_label(score: float, guardrails: list[GuardrailResult]) -> str:
    # force_caution guardrail overrides everything
    if any(g.triggered and g.action == "force_caution" for g in guardrails):
        return "CAUTION"

    if score >= 70:
        label = "FAVORABLE"
    elif score >= 40:
        label = "NEUTRAL"
    else:
        label = "WAIT"

    # downgrade_label guardrail steps down one level
    if any(g.triggered and g.action == "downgrade_label" for g in guardrails):
        label = {"FAVORABLE": "NEUTRAL", "NEUTRAL": "WAIT", "WAIT": "WAIT"}[label]

    return label


def compute_confidence(risk: float, data_warning: Optional[str] = None) -> str:
    # Data scarcity always forces LOW confidence
    if data_warning is not None:
        return "LOW"
    if risk < 30:
        return "HIGH"
    if risk < 60:
        return "MEDIUM"
    return "LOW"
