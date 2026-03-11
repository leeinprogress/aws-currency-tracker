# PRD.md — Product Requirements Document
## AWS Currency Tracker

**Version:** 3.0
**Updated:** 2026-03-02
**Status:** Final

---

## 1. Overview

### 1.1 Product Summary

AWS Currency Tracker is a **pure serverless** backend service that:
- Monitors KRW exchange rates (USD, EUR, JPY, CNY vs KRW)
- Sends Telegram alerts when user-defined target rates are hit
- Provides a **Scoring + Guardrail engine** recommending optimal remittance timing

### 1.2 Architecture Decision: Why Pure Serverless

The existing codebase already runs FastAPI on Lambda via Mangum + API Gateway. The workload
profile — sporadic API traffic, lightweight compute, no persistent connections — is textbook
Lambda territory. EC2 was considered to show "AWS breadth" but removed because:

- VPC subnetting, NAT Gateway, ALB, CodeDeploy complexity adds no business value here
- "Why both Lambda and EC2?" has no satisfying answer when Lambda already works
- Smaller stack = deeper understanding per service = stronger portfolio story

### 1.3 Goals

| Goal | Description |
|---|---|
| Portfolio | Demonstrate production-level AWS serverless engineering |
| Domain Depth | Show Fintech understanding via rule-based scoring + guardrails |
| AWS Depth | Go deep on Lambda, DynamoDB, EventBridge, SQS, CloudWatch, IAM |
| Code Quality | Tested, documented, secure, maintainable |

### 1.4 Out of Scope

- Frontend / web dashboard
- EC2, ALB, VPC, NAT Gateway, CodeDeploy
- Monetization or billing
- Real-time rate data
- Backtest pipeline
- Fee/commission auto-collection
- Currency pairs beyond USD, EUR, JPY, CNY vs KRW
- X-Ray tracing, CloudFront

---

## 2. Target Users

**Primary — Korean Expat / Remittance User**
Koreans living abroad who regularly send money home and want to remit at the best rate.
Interacts via Swagger UI or Postman.

**Secondary — Technical Reviewer**
Engineers evaluating this as a portfolio piece. Looks for clean serverless architecture,
domain understanding, and production-readiness.

---

## 3. Functional Requirements

### 3.1 Authentication

| ID | Requirement | Priority |
|---|---|---|
| AUTH-01 | Register with email + password | Must |
| AUTH-02 | bcrypt password hashing | Must |
| AUTH-03 | Login → JWT access (15min) + refresh token (7d) | Must |
| AUTH-04 | POST /auth/refresh — new access token | Must |
| AUTH-05 | POST /auth/logout — invalidate refresh token | Must |
| AUTH-06 | Google OAuth 2.0 as optional login | Should |
| AUTH-07 | Rate limiting: login 5/min, register 3/min | Must |

### 3.2 Alert Management

| ID | Requirement | Priority |
|---|---|---|
| ALERT-01 | Create alert: currency, direction, target rate | Must |
| ALERT-02 | List / get / update / delete / toggle alerts | Must |
| ALERT-03 | Reject duplicates (same user + currency + direction + target) | Must |
| ALERT-04 | Idempotency-Key header on POST /alerts (5min DDB cache) | Must |
| ALERT-05 | Optional label per alert | Nice |

### 3.3 Exchange Rates

| ID | Requirement | Priority |
|---|---|---|
| RATE-01 | Fetch daily rates (mid + buy + sell + spread) from Korea Exim Bank via Lambda | Must |
| RATE-02 | Current rates endpoint | Must |
| RATE-03 | 90-day history endpoint | Must |
| RATE-04 | Statistical analysis endpoint: MA7/MA30, percentile, z-score, vol, spread_ratio | Must |
| RATE-05 | Rate cache TTL 25h via DynamoDB | Must |

### 3.4 Scoring + Guardrail Engine

| ID | Requirement | Priority |
|---|---|---|
| SCORE-01 | Feature engineering: percentile, z_score, MA7/MA30, ma_slope, vol_ratio, spread_ratio | Must |
| SCORE-02 | value_score (0–100): percentile. Higher rate = more KRW received = favorable (USD→KRW direction, no parameterization) | Must |
| SCORE-03 | trend_score (0–100): MA slope + spot vs MA30 | Must |
| SCORE-04 | risk_score (0–100): vol_ratio + spread_ratio | Must |
| SCORE-05 | raw = (0.5 × value) + (0.3 × trend) − (0.4 × risk); final = (raw + 40) / 120 × 100 → normalized [0-100] | Must |
| SCORE-06 | Label: FAVORABLE ≥70 / NEUTRAL 40–69 / WAIT <40 | Must |
| SCORE-07 | Guardrail: vol_ratio > 1.5 → downgrade label one step | Must |
| SCORE-08 | Guardrail: spread_ratio > 1.35 → −15 penalty | Must |
| SCORE-09 | Guardrail: risk_score > 80 → force CAUTION | Must |
| SCORE-10 | confidence: HIGH / MEDIUM / LOW (inverse of risk_score) | Must |
| SCORE-11 | explanations: 2–4 English sentences justifying score | Must |
| SCORE-12 | GET /recommendations/{currency} | Must |
| SCORE-13 | Guardrails run before final score and override regardless of signals | Must |
| SCORE-14 | Data guards: 0 records→503, <7 records→422, 7-29 records→proceed with confidence=LOW + data_warning, stale>2d→data_warning | Must |
| SCORE-15 | rate_unit field in response: "per 100 JPY" for JPY, "per 1 unit" for USD/EUR/CNY | Must |
| SCORE-16 | /rates/{currency}/analysis reuses compute_features() from scoring/features.py — single implementation | Must |

### 3.5 Notifications + Reliability

| ID | Requirement | Priority |
|---|---|---|
| NOTIFY-01 | EventBridge → check_alerts after fetch_rates | Must |
| NOTIFY-02 | Telegram notification on alert condition match | Must |
| NOTIFY-03 | Write to notification-history table after each send | Must |
| NOTIFY-04 | NotificationService ABC (Telegram is only implementation) | Must |
| NOTIFY-05 | SQS DLQ on check_alerts — no silent failures | Must |
| NOTIFY-06 | dlq_handler Lambda logs failed payloads to CloudWatch | Must |

### 3.6 User Profile

| ID | Requirement | Priority |
|---|---|---|
| USER-01 | GET /users/me | Must |
| USER-02 | PUT /users/me — update telegram_chat_id | Must |
| USER-03 | DELETE /users/me — cascade to all alerts | Must |

### 3.7 Documentation

| ID | Requirement | Priority |
|---|---|---|
| DOC-01 | All endpoints under /api/v1/ | Must |
| DOC-02 | Swagger UI at /docs, ReDoc at /redoc | Must |
| DOC-03 | GET /health → 200 with status/env/version | Must |
| DOC-04 | SLO.md with error budget | Must |
| DOC-05 | DOCS/scoring-engine.md | Must |

---

## 4. Non-Functional Requirements

### 4.1 Security

| ID | Requirement |
|---|---|
| SEC-01 | API Gateway enforces HTTPS — no plaintext |
| SEC-02 | bcrypt for passwords, never logged |
| SEC-03 | JWT refresh token stored as bcrypt hash in DDB |
| SEC-04 | All secrets in SSM Parameter Store |
| SEC-05 | CORS restricted — no wildcard in prod |
| SEC-06 | Pydantic validation on all inputs |
| SEC-07 | Errors never expose stack traces |
| SEC-08 | Idempotency-Key on POST /alerts |

### 4.2 Reliability

| ID | Requirement |
|---|---|
| REL-01 | SQS DLQ on check_alerts — zero silent alert drops |
| REL-02 | dlq_handler logs all DLQ events to CloudWatch |
| REL-03 | DynamoDB PITR on all 5 tables |
| REL-04 | DynamoDB DeletionProtection in prod |

### 4.3 Observability

| ID | Requirement |
|---|---|
| OBS-01 | Structured JSON logs via structlog → CloudWatch |
| OBS-02 | Alarm: Lambda errors > 0 / 5min → SNS |
| OBS-03 | Alarm: Lambda p95 duration > 10s → SNS |
| OBS-04 | Alarm: DynamoDB throttled requests > 0 → SNS |
| OBS-05 | Alarm: API Gateway 5xx rate > 1% / 5min → SNS |
| OBS-06 | Alarm: DLQ message count > 0 → SNS |
| OBS-07 | CloudWatch Dashboard: Lambda + DynamoDB + API GW + DLQ |
| OBS-08 | SLO.md: 99% alert delivery within 5min, error budget defined |

### 4.4 IAM (Least Privilege per Lambda)

| Lambda | Allowed |
|---|---|
| FastAPI | DynamoDB CRUD (all 5 tables) + SSM read |
| fetch_rates | DynamoDB CRUD (exchange-rates + rate-history) + SSM read |
| check_alerts | DynamoDB CRUD (alerts + users + notification-history + exchange-rates) + SSM read |
| dlq_handler | CloudWatch Logs write only |

---

## 5. AWS Services

| Service | Purpose | Demonstrates |
|---|---|---|
| Lambda (×4) | FastAPI + fetch_rates + check_alerts + dlq_handler | Serverless compute |
| API Gateway | HTTPS entry point + Lambda proxy | Serverless API |
| DynamoDB | All persistence (5 tables) | NoSQL, GSI, TTL, PITR |
| SQS | DLQ for check_alerts | Reliability design |
| EventBridge | Scheduling + event fan-out | Event-driven architecture |
| CloudWatch | Logs + Alarms + Dashboard | Observability |
| SSM Parameter Store | Secrets | Secure config |
| IAM | Per-Lambda least-privilege | Security |
| SNS | Alarm → email | Pub/sub |
| Route 53 | Custom domain DNS | Domain routing |
| ACM | TLS cert (API Gateway custom domain) | HTTPS |
| GitHub Actions | CI/CD via sam deploy | Automation |

---

## 6. Data Flow

```
EventBridge Schedule (11AM KST daily)
    → fetch_rates Lambda
        → Korea Exim Bank API (mid + buy/sell + spread)
        → DynamoDB: exchange-rates (TTL 25h) + rate-history
        → EventBridge: publish "RatesFetched" event

EventBridge Rule ("RatesFetched")
    → check_alerts Lambda
        → DynamoDB: read active alerts (sparse GSI)
        → Compare each alert vs current rate
        → Match: TelegramNotificationService.send()
        → Write notification-history record
        → Failure: → SQS DLQ → dlq_handler → CloudWatch log

Client → API Gateway → FastAPI Lambda
    → GET /recommendations/USD
        → Load rate-history (90d) from DDB
        → features.py → signals.py → guardrails.py → scorer.py → explainer.py
        → Return JSON with label, score, confidence, explanations
```

---

## 7. Success Criteria

1. All endpoints live on HTTPS custom domain
2. Swagger UI publicly accessible, fully documented
3. Full end-to-end: register → create alert → fetch triggered → Telegram received
4. GET /recommendations returns valid scored result with explanations
5. DLQ verified: force failure → event captured → dlq_handler logs it
6. All 4 CloudWatch alarms + DLQ alarm active and tested
7. All secrets in SSM — zero in codebase
8. SLO.md complete with error budget
9. Architecture diagram accurate in README
10. All tests pass: `pytest -v`
