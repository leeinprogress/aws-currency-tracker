from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ExchangeRateResponse(BaseModel):
    currency_code: str
    currency_name: str
    tts: float
    ttb: float
    deal_bas_r: float
    updated_at: Optional[datetime] = None


class ExchangeRateListResponse(BaseModel):
    rates: list[ExchangeRateResponse]
    total: int
    cached: bool
    cache_updated_at: Optional[datetime] = None


class RateHistoryItem(BaseModel):
    currency_code: str
    currency_name: str
    timestamp: datetime
    tts: float
    ttb: float
    deal_bas_r: float
    source_date: str
    change_percent: Optional[float] = Field(
        None, description="Percent change from previous record"
    )


class RateHistoryResponse(BaseModel):
    currency_code: str
    history: list[RateHistoryItem]
    total: int
    start_date: datetime
    end_date: datetime


class RateAnalysisResponse(BaseModel):
    currency: str
    ma7: float
    ma30: float
    percentile_90d: float
    z_score: float
    volatility_7d: float
    volatility_30d: float
    vol_ratio: float
    spread_current: float
    spread_avg_90d: float
    spread_ratio: float
