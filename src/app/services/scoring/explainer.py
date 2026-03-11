from app.services.scoring.features import ScoringFeatures
from app.services.scoring.guardrails import GuardrailResult


def generate_explanations(
    features: ScoringFeatures,
    guardrails: list[GuardrailResult],
) -> list[str]:
    sentences: list[str] = []

    rate_unit = "per 100 JPY" if features.currency == "JPY" else "per 1 unit"

    # Always: percentile context
    if features.percentile >= 80:
        sentences.append(
            f"Current rate ({features.spot_rate:.2f} KRW {rate_unit}) is in the top "
            f"{100 - features.percentile:.0f}% of the past 90 days — favorable for receiving KRW."
        )
    elif features.percentile <= 20:
        sentences.append(
            f"Current rate ({features.spot_rate:.2f} KRW {rate_unit}) is in the bottom "
            f"{features.percentile:.0f}% — historically low for KRW receipt."
        )
    else:
        sentences.append(
            f"Current rate ({features.spot_rate:.2f} KRW {rate_unit}) is at the "
            f"{features.percentile:.0f}th percentile of the past 90 days."
        )

    # Trend
    if features.ma_slope < -0.5 and features.spot_rate < features.ma30:
        sentences.append("Short-term downward trend (MA7 below MA30) — rate may continue falling.")
    elif features.ma_slope > 0.5 and features.spot_rate > features.ma30:
        sentences.append("Short-term upward trend — rate is rising above the 30-day average.")

    # Triggered guardrail explanations
    for g in guardrails:
        if g.triggered and g.explanation:
            sentences.append(g.explanation)

    return sentences[:4]  # max 4
