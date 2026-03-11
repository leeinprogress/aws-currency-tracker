import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.exceptions import InsufficientDataError, ScoringUnavailableError
from app.domain.entities.rate_history import RateHistory


@dataclass
class ScoringFeatures:
    currency: str
    spot_rate: float
    buy_rate: float
    sell_rate: float
    percentile: float       # 0–100, rank of spot in 90d history (high = historically expensive)
    z_score: float          # (spot - MA90) / STD90
    ma7: float
    ma30: float
    ma90: float
    ma_slope: float         # (ma7_today - ma7_5d_ago) / 5
    volatility_7d: float
    volatility_30d: float
    vol_ratio: float        # volatility_7d / volatility_30d
    spread_current: float   # sell - buy
    spread_avg_90d: float
    spread_ratio: float     # spread_current / spread_avg_90d
    data_warning: Optional[str] = None


def compute_features(
    currency: str,
    history: list[RateHistory],  # sorted ascending by date, min 7 required
    current_rate: float,          # spot rate from exchange-rates table
) -> ScoringFeatures:
    """Compute all scoring features from rate history."""
    if len(history) == 0:
        raise ScoringUnavailableError(f"No rate history available for {currency}")

    if len(history) < 7:
        raise InsufficientDataError(
            f"Insufficient data for {currency}: {len(history)} records (min 7 required)",
            min_required=7,
            actual=len(history),
        )

    data_warning: Optional[str] = None

    if len(history) < 30:
        data_warning = "Less than 30 days of history"

    # Stale data check: last record older than 2 days
    now = datetime.now(timezone.utc)
    last_ts = history[-1].timestamp
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)
    if (now - last_ts) > timedelta(days=2):
        stale_msg = f"Rate data is stale (last updated: {history[-1].source_date})"
        data_warning = stale_msg if data_warning is None else f"{data_warning}; {stale_msg}"

    rates = [r.deal_bas_r for r in history]
    n = len(rates)

    # Moving averages
    ma7 = sum(rates[-min(7, n) :]) / min(7, n)
    ma30 = sum(rates[-min(30, n) :]) / min(30, n)
    ma90 = sum(rates) / n

    # MA slope: (ma7_today - ma7_5d_ago) / 5
    # Requires at least 12 entries (7 for today + 5 offset)
    if n >= 12:
        ma7_5d_ago = sum(rates[n - 12 : n - 5]) / 7
        ma_slope = (ma7 - ma7_5d_ago) / 5
    else:
        ma_slope = 0.0

    # Percentile: fraction of history rates strictly below current_rate
    rank = sum(1 for r in rates if r < current_rate)
    percentile = (rank / n) * 100

    # Z-score (population std; guard for zero std)
    std_90 = statistics.pstdev(rates) if n > 1 else 0.0
    z_score = (current_rate - ma90) / std_90 if std_90 else 0.0

    # Volatility: pstdev of absolute daily changes
    def _volatility(window: int) -> float:
        w = rates[-min(window, n) :]
        if len(w) < 2:
            return 0.0
        changes = [abs(w[i] - w[i - 1]) for i in range(1, len(w))]
        return statistics.pstdev(changes)

    volatility_7d = _volatility(7)
    volatility_30d = _volatility(30)
    vol_ratio = (volatility_7d / volatility_30d) if volatility_30d else 1.0

    # Spread
    buy_rate = history[-1].ttb
    sell_rate = history[-1].tts
    spread_current = sell_rate - buy_rate
    spreads = [r.tts - r.ttb for r in history]
    spread_avg_90d = sum(spreads) / len(spreads)
    spread_ratio = (spread_current / spread_avg_90d) if spread_avg_90d else 1.0

    return ScoringFeatures(
        currency=currency,
        spot_rate=current_rate,
        buy_rate=buy_rate,
        sell_rate=sell_rate,
        percentile=percentile,
        z_score=z_score,
        ma7=ma7,
        ma30=ma30,
        ma90=ma90,
        ma_slope=ma_slope,
        volatility_7d=volatility_7d,
        volatility_30d=volatility_30d,
        vol_ratio=vol_ratio,
        spread_current=spread_current,
        spread_avg_90d=spread_avg_90d,
        spread_ratio=spread_ratio,
        data_warning=data_warning,
    )
