from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SubScores(BaseModel):
    value_score: float
    trend_score: float
    risk_score: float


class RateContext(BaseModel):
    ma7: float
    ma30: float
    percentile: float
    z_score: float
    spread_ratio: float
    vol_ratio: float


class RecommendationResponse(BaseModel):
    currency: str
    evaluated_at: datetime
    spot_rate: float
    label: str          # FAVORABLE | NEUTRAL | WAIT | CAUTION
    final_score: float
    confidence: str     # HIGH | MEDIUM | LOW
    sub_scores: SubScores
    guardrails_triggered: list[str]
    explanations: list[str]
    rate_context: RateContext
    rate_unit: str      # "per 100 JPY" | "per 1 unit"
    data_warning: Optional[str] = None


