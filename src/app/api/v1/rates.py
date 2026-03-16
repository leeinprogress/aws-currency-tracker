from datetime import datetime, timedelta, UTC

from fastapi import APIRouter, HTTPException, Depends, Query

from app.core.dependencies import get_current_user
from app.domain.entities.user import User
from app.schemas.rate import (
    ExchangeRateResponse,
    ExchangeRateListResponse,
    RateAnalysisResponse,
    RateHistoryResponse,
    RateHistoryItem,
)
from app.services.rate_service import RateService
from app.services.scoring.features import compute_features

router = APIRouter()


def get_rate_service() -> RateService:
    return RateService()


@router.get("", response_model=ExchangeRateListResponse)
async def list_rates(
    service: RateService = Depends(get_rate_service)
):
    rates, cached, cache_time = await service.get_all_rates()
    
    if not rates:
        raise HTTPException(status_code=503, detail="Exchange rate data unavailable")
    
    return ExchangeRateListResponse(
        rates=[
            ExchangeRateResponse(
                currency_code=rate.cur_unit,
                currency_name=rate.cur_nm,
                tts=rate.tts,
                ttb=rate.ttb,
                deal_bas_r=rate.deal_bas_r,
                updated_at=cache_time
            )
            for rate in rates
        ],
        total=len(rates),
        cached=cached,
        cache_updated_at=cache_time
    )


@router.get("/{currency_code}", response_model=ExchangeRateResponse)
async def get_rate(
    currency_code: str,
    service: RateService = Depends(get_rate_service)
):
    rate = await service.get_rate_by_currency(currency_code)

    if not rate:
        raise HTTPException(status_code=404, detail=f"Currency '{currency_code}' not found")

    _, _, cache_time = await service.get_all_rates()

    return ExchangeRateResponse(
        currency_code=rate.cur_unit,
        currency_name=rate.cur_nm,
        tts=rate.tts,
        ttb=rate.ttb,
        deal_bas_r=rate.deal_bas_r,
        updated_at=cache_time
    )


@router.get("/{currency_code}/history", response_model=RateHistoryResponse)
async def get_rate_history(
    currency_code: str,
    days: int = Query(default=30, ge=1, le=90, description="Number of days to look back"),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum records to return"),
    service: RateService = Depends(get_rate_service)
):
    """
    Get historical exchange rate data for a currency.

    Returns time-series data for analyzing rate trends over time.
    Data is sorted by timestamp (newest first).
    """
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days)

    history = await service.get_rate_history(
        currency_code=currency_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    if not history:
        raise HTTPException(
            status_code=404,
            detail=f"No historical data found for currency '{currency_code}'"
        )

    # Build response with change percentages
    history_items = []
    for i, record in enumerate(history):
        change_percent = None
        if i < len(history) - 1:
            previous = history[i + 1]  # List is sorted newest first
            change_percent = record.calculate_change(previous)

        history_items.append(
            RateHistoryItem(
                currency_code=record.currency_code,
                currency_name=record.currency_name,
                timestamp=record.timestamp,
                tts=record.tts,
                ttb=record.ttb,
                deal_bas_r=record.deal_bas_r,
                source_date=record.source_date,
                change_percent=change_percent,
            )
        )

    return RateHistoryResponse(
        currency_code=currency_code.upper(),
        history=history_items,
        total=len(history_items),
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/{currency_code}/analysis", response_model=RateAnalysisResponse)
async def get_rate_analysis(
    currency_code: str,
    current_user: User = Depends(get_current_user),
    service: RateService = Depends(get_rate_service),
):
    """Compute moving averages, percentile, z-score, volatility, and spread stats."""
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=90)

    history = await service.get_rate_history(
        currency_code=currency_code,
        start_date=start_date,
        end_date=end_date,
        limit=500,
    )

    # history is newest-first; reverse for ascending order expected by compute_features
    hist_asc = list(reversed(history))
    current_rate = hist_asc[-1].deal_bas_r if hist_asc else 0.0


    features = compute_features(
        currency=currency_code.upper(),
        history=hist_asc,
        current_rate=current_rate,
    )

    return RateAnalysisResponse(
        currency=features.currency,
        ma7=round(features.ma7, 4),
        ma30=round(features.ma30, 4),
        percentile_90d=round(features.percentile, 2),
        z_score=round(features.z_score, 4),
        volatility_7d=round(features.volatility_7d, 4),
        volatility_30d=round(features.volatility_30d, 4),
        vol_ratio=round(features.vol_ratio, 4),
        spread_current=round(features.spread_current, 4),
        spread_avg_90d=round(features.spread_avg_90d, 4),
        spread_ratio=round(features.spread_ratio, 4),
    )