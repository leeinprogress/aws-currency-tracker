from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_current_user
from app.domain.entities.user import User
from app.schemas.recommendations import (
    RateContext,
    RecommendationResponse,
    SubScores,
)
from app.services.rate_service import RateService
from app.services.scoring.explainer import generate_explanations
from app.services.scoring.features import compute_features
from app.services.scoring.guardrails import apply_guardrails
from app.services.scoring.scorer import compute_confidence, compute_final_score, compute_label
from app.services.scoring.signals import risk_score, trend_score, value_score

router = APIRouter()

SUPPORTED_CURRENCIES = ["USD", "EUR", "JPY", "CNY"]


def get_rate_service() -> RateService:
    return RateService()


@router.get("/{currency}", response_model=RecommendationResponse)
async def get_recommendation(
    currency: str,
    current_user: User = Depends(get_current_user),
    service: RateService = Depends(get_rate_service),
) -> RecommendationResponse:
    currency = currency.upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported currency '{currency}'. Must be one of {SUPPORTED_CURRENCIES}",
        )

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=90)

    history = await service.get_rate_history(
        currency_code=currency,
        start_date=start_date,
        end_date=end_date,
        limit=500,
    )

    # history is newest-first; reverse for ascending order expected by compute_features
    hist_asc = list(reversed(history))

    # Prefer current rate from exchange-rates table; fall back to most recent history
    current = await service.get_rate_by_currency(currency)
    current_rate = current.deal_bas_r if current is not None else (
        hist_asc[-1].deal_bas_r if hist_asc else 0.0
    )

    features = compute_features(currency, hist_asc, current_rate)

    v = value_score(features)
    t = trend_score(features)
    r = risk_score(features)

    guardrails = apply_guardrails(features, r)
    final_score = compute_final_score(v, t, r, guardrails)
    label = compute_label(final_score, guardrails)
    confidence = compute_confidence(r, features.data_warning)
    explanations = generate_explanations(features, guardrails)

    rate_unit = "per 100 JPY" if currency == "JPY" else "per 1 unit"

    return RecommendationResponse(
        currency=currency,
        evaluated_at=datetime.now(timezone.utc),
        spot_rate=round(current_rate, 4),
        label=label,
        final_score=round(final_score, 2),
        confidence=confidence,
        sub_scores=SubScores(
            value_score=round(v, 2),
            trend_score=round(t, 2),
            risk_score=round(r, 2),
        ),
        guardrails_triggered=[g.name for g in guardrails if g.triggered],
        explanations=explanations,
        rate_context=RateContext(
            ma7=round(features.ma7, 4),
            ma30=round(features.ma30, 4),
            percentile=round(features.percentile, 2),
            z_score=round(features.z_score, 4),
            spread_ratio=round(features.spread_ratio, 4),
            vol_ratio=round(features.vol_ratio, 4),
        ),
        rate_unit=rate_unit,
        data_warning=features.data_warning,
    )
