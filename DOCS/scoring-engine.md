# Scoring Engine — Technical Reference

## Overview

The scoring engine evaluates whether the current exchange rate is a favorable
time for a Korean expat to remit money home. It runs on every call to
`GET /api/v1/recommendations/{currency}`.

**Direction assumption:** The user is *receiving* KRW (sending USD/EUR/JPY/CNY
to Korea). A higher USD/KRW rate means more KRW per dollar — favorable.

---

## Pipeline

```
Rate History (90d) + Current Rate
    | features.py       — compute statistical features
    | signals.py        — convert features to sub-scores (0-100 each)
    | guardrails.py     — apply hard rules BEFORE final score
    | scorer.py         — compute final_score + label + confidence
    | explainer.py      — generate 2-4 English explanation sentences
```

---

## Features (features.py)

| Feature | Description |
|---|---|
| `percentile` | Rank of current rate in 90-day history (0-100). 100 = highest rate seen. |
| `z_score` | Standard deviations from 90-day mean |
| `ma7` | 7-day moving average |
| `ma30` | 30-day moving average |
| `ma_slope` | (ma7_today - ma7_5d_ago) / 5 — rate of change |
| `vol_ratio` | volatility_7d / volatility_30d — recent vs historical volatility |
| `spread_ratio` | spread_current / spread_avg_90d — bid/ask spread vs average |

---

## Signals (signals.py)

| Score | Formula | Interpretation |
|---|---|---|
| `value_score` | = percentile | High rate = more KRW = good |
| `trend_score` | Rising MA + spot above MA30 = higher | Momentum favors sender |
| `risk_score` | vol_ratio + spread components | High = uncertain conditions |

---

## Guardrails (guardrails.py)

Guardrails run **before** the final score. They override optimistic signals
when market conditions are abnormal.

| Rule | Threshold | Action |
|---|---|---|
| High volatility | vol_ratio > 1.5 | Downgrade label one step |
| Wide spread | spread_ratio > 1.35 | Apply -15 penalty to final_score |
| Composite risk | risk_score > 80 | Force label = CAUTION |

---

## Final Score (scorer.py)

```
raw   = (0.5 x value_score) + (0.3 x trend_score) - (0.4 x risk_score)
final = (raw + 40) / 120 x 100   -> normalized to [0-100]
```

Spread penalty (-15) applied after normalization if guardrail triggered.

| Label | Condition |
|---|---|
| FAVORABLE | final_score >= 70 |
| NEUTRAL | 40 <= final_score < 70 |
| WAIT | final_score < 40 |
| CAUTION | risk guardrail override |

**Confidence:** HIGH (risk < 30) / MEDIUM (30-60) / LOW (> 60)

---

## Data Guards

Applied before scoring. Returns early if data quality is insufficient.

| Condition | Response |
|---|---|
| 0 records | 503 Service Unavailable |
| < 7 records | 503 Service Unavailable |
| 7-29 records | 200 with `confidence = LOW` + `data_warning` |
| Stale > 2 days | 200 with `data_warning` |

503 is intentional — insufficient history is a server-side problem,
not a client input error.

---

## Example: FAVORABLE Day

**Scenario:** USD/KRW at 1,380 — near 90-day high, moderate volatility.

```json
{
  "label": "FAVORABLE",
  "final_score": 76.4,
  "confidence": "HIGH",
  "guardrails_triggered": [],
  "explanations": [
    "Current rate (1380.00 KRW per 1 unit) is in the top 12% of the past 90 days — favorable for receiving KRW.",
    "Short-term upward trend — MA7 is above MA30, rate is rising."
  ]
}
```

---

## Example: CAUTION Day

**Scenario:** Rate looks high (percentile 80) but vol_ratio is 2.1 — extreme volatility.

```json
{
  "label": "CAUTION",
  "final_score": 51.0,
  "confidence": "LOW",
  "guardrails_triggered": ["high_volatility", "high_risk"],
  "explanations": [
    "Current rate appears favorable historically, but 7-day volatility is 2.1x the 30-day average.",
    "Composite risk score exceeds threshold — rate may move significantly in either direction.",
    "Consider waiting for volatility to normalize before transferring."
  ]
}
```
