from dataclasses import dataclass

from app.services.scoring.features import ScoringFeatures


@dataclass
class GuardrailResult:
    name: str
    triggered: bool
    action: str        # "downgrade_label" | "spread_penalty" | "force_caution"
    explanation: str


def apply_guardrails(features: ScoringFeatures, risk: float) -> list[GuardrailResult]:
    results: list[GuardrailResult] = []

    # Rule 1: Elevated volatility
    triggered = features.vol_ratio > 1.5
    results.append(GuardrailResult(
        name="high_volatility",
        triggered=triggered,
        action="downgrade_label",
        explanation=(
            f"7-day volatility is {features.vol_ratio:.1f}x the 30-day average — "
            "signal reliability is reduced."
        ) if triggered else "",
    ))

    # Rule 2: Wide spread
    triggered = features.spread_ratio > 1.35
    pct = (features.spread_ratio - 1) * 100
    results.append(GuardrailResult(
        name="wide_spread",
        triggered=triggered,
        action="spread_penalty",
        explanation=(
            f"Current spread is +{pct:.0f}% wider than the 90-day average — "
            "effective rate is worse than spot."
        ) if triggered else "",
    ))

    # Rule 3: High composite risk
    triggered = risk > 80
    results.append(GuardrailResult(
        name="high_risk",
        triggered=triggered,
        action="force_caution",
        explanation=(
            "Composite risk score exceeds safe threshold — "
            "conditions are too volatile to recommend."
        ) if triggered else "",
    ))

    return results
