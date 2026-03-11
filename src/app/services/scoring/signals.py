from app.services.scoring.features import ScoringFeatures


def value_score(features: ScoringFeatures) -> float:
    # Target user: Korean expat sending USD→KRW. Higher rate = more KRW received = favorable.
    # score = percentile  (high percentile = rate is historically high = favorable)
    # Clamp to [0, 100]
    return max(0.0, min(100.0, features.percentile))


def trend_score(features: ScoringFeatures) -> float:
    # Falling MA slope + spot below MA30 → rate may improve (mean reversion) → higher score
    # Rising MA + spot above MA30 → rate is high and rising; send now before it falls → lower score
    # Normalize to [0, 100] centered at 50

    # Invert slope: negative (falling) slope gives positive contribution
    slope_component = max(-50.0, min(50.0, -features.ma_slope * 10))

    # Below MA30 gives positive contribution (potential for mean reversion upward)
    spot_vs_ma30 = features.ma30 - features.spot_rate
    if features.volatility_30d > 0:
        ma30_component = max(-50.0, min(50.0, (spot_vs_ma30 / features.volatility_30d) * 25))
    else:
        ma30_component = 25.0 if features.spot_rate < features.ma30 else -25.0

    raw = 50.0 + slope_component + ma30_component
    return max(0.0, min(100.0, raw))


def risk_score(features: ScoringFeatures) -> float:
    # vol_component: scales with vol_ratio (1.0 = normal → 40 points, 2.5 = high → 100 points)
    vol_component = min(100.0, features.vol_ratio * 40)
    # spread_component: excess spread above average
    spread_component = (
        min(100.0, (features.spread_ratio - 1) * 100) if features.spread_ratio > 1 else 0.0
    )
    return min(100.0, (vol_component + spread_component) / 2)
