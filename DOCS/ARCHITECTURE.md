# Architecture & Design Decisions

## Project Overview

AWS Currency Tracker is a production-grade **pure serverless** backend that:
1. Tracks KRW exchange rates (USD, EUR, JPY, CNY)
2. Sends Telegram alerts when user-defined target rates are hit
3. Provides a scoring + guardrail engine recommending optimal remittance timing

Target users: Korean expats monitoring KRW exchange rates for remittance timing.

---

## Project Structure

```
aws-currency-tracker/
├── src/
│   ├── app/
│   │   ├── api/v1/               # FastAPI routers
│   │   │   ├── router.py         # Aggregates all routers
│   │   │   ├── auth.py           # /auth/* endpoints
│   │   │   ├── alerts.py         # /alerts/* endpoints
│   │   │   ├── rates.py          # /rates/* endpoints
│   │   │   ├── users.py          # /users/* endpoints
│   │   │   ├── notifications.py  # /notifications endpoint
│   │   │   └── recommendations.py # /recommendations/* endpoints
│   │   ├── clients/
│   │   │   └── exchange_rate_client.py  # Korea Exim Bank API
│   │   ├── core/
│   │   │   ├── config.py         # Pydantic Settings (SSM-aware)
│   │   │   ├── security.py       # JWT, bcrypt, Google OAuth
│   │   │   ├── dependencies.py   # FastAPI DI (repos, services, auth)
│   │   │   └── exceptions.py     # Domain exceptions
│   │   ├── domain/
│   │   │   ├── entities/         # Alert, User, RateHistory
│   │   │   ├── repositories.py   # Repository interfaces (protocols)
│   │   │   └── notification.py   # NotificationService ABC
│   │   ├── infrastructure/
│   │   │   ├── persistence/      # DynamoDB repository implementations
│   │   │   │   ├── dynamodb_alert_repository.py
│   │   │   │   ├── dynamodb_user_repository.py
│   │   │   │   ├── dynamodb_rate_history_repository.py
│   │   │   │   ├── dynamodb_notification_history_repository.py
│   │   │   │   ├── mappers.py    # DynamoDB ↔ domain entity mapping
│   │   │   │   └── repositories.py  # Factory functions
│   │   │   ├── notifications/
│   │   │   │   └── telegram.py   # TelegramNotificationService
│   │   │   └── logging/          # structlog JSON logging + middleware
│   │   ├── schemas/              # Pydantic request/response models
│   │   │   ├── auth.py, alerts.py, rates.py, users.py
│   │   │   ├── notification.py
│   │   │   └── recommendations.py
│   │   ├── services/
│   │   │   ├── alert_service.py
│   │   │   ├── rate_service.py
│   │   │   ├── user_service.py
│   │   │   └── scoring/          # Scoring engine pipeline
│   │   │       ├── features.py   # Statistical feature computation
│   │   │       ├── signals.py    # Sub-scores (value, trend, risk)
│   │   │       ├── guardrails.py # Hard rule overrides
│   │   │       ├── scorer.py     # Final score + label
│   │   │       └── explainer.py  # English explanation generation
│   │   └── main.py               # FastAPI app + Mangum handler
│   └── functions/
│       ├── fetch_rates.py        # Daily rate collection (EventBridge Schedule)
│       ├── check_alerts.py       # Alert evaluation (EventBridge Rule)
│       ├── weekly_report.py      # Weekly Telegram summary (Monday 9AM KST)
│       └── dlq_handler.py        # Logs failed events from SQS DLQ
├── tests/
│   ├── conftest.py
│   ├── test_api_endpoints.py
│   ├── test_functions.py
│   ├── test_repositories.py
│   ├── test_services.py
│   ├── test_security.py
│   └── test_scoring/             # 75 scoring engine tests
│       ├── test_features.py, test_signals.py
│       ├── test_guardrails.py, test_scorer.py
├── .github/workflows/
│   ├── ci.yml                    # Lint + test on push/PR to main
│   └── cd.yml                    # Deploy on CI pass (dev: main, prod: release)
├── DOCS/
│   ├── scoring-engine.md         # Scoring engine technical reference
│   └── ARCHITECTURE.md           # This file
├── template.yaml                 # AWS SAM — all infrastructure
├── SLO.md                        # Service Level Objectives
└── CLAUDE.md                     # AI assistant instructions
```

---

## AWS Architecture

```
Client (Postman / Swagger UI)
    | HTTPS
[API Gateway] → Lambda proxy
    |
[FastAPI Lambda — Mangum adapter]
    ├── /api/v1/auth/*
    ├── /api/v1/alerts/*
    ├── /api/v1/rates/*
    ├── /api/v1/users/*
    ├── /api/v1/notifications/*
    ├── /api/v1/recommendations/*
    └── /health
    |
[DynamoDB — 5 tables]

[Scheduled Lambdas]
fetch_rates     ← EventBridge Schedule (daily 11AM KST)
    | publishes "RatesFetched" event to custom bus
check_alerts    ← EventBridge Rule
    └── on failure → [SQS DLQ] → dlq_handler Lambda → CloudWatch Logs
weekly_report   ← EventBridge Schedule (Monday 9AM KST)

[Observability]
CloudWatch Logs (all Lambdas, structlog JSON)
CloudWatch Alarms (7) → SNS → email (OpsEmail)
CloudWatch Dashboard (per-env)

[CI/CD]
GitHub Actions → sam build → sam deploy
  CI: lint (ruff) + test (pytest) on push/PR to main
  CD: deploy-dev (main branch), deploy-prod (release branch)
```

---

## AWS Services

| Service | Purpose |
|---|---|
| Lambda (×5) | FastAPI API + fetch_rates + check_alerts + dlq_handler + weekly_report |
| API Gateway | HTTPS entry point, Lambda proxy integration |
| DynamoDB (5 tables) | All persistence (users, alerts, exchange-rates, rate-history, notification-history) |
| EventBridge | Schedule (fetch_rates, weekly_report) + Rule (check_alerts) + custom event bus |
| SQS | Dead Letter Queue for check_alerts failures |
| CloudWatch | Logs + 7 Alarms + Dashboard |
| SNS | Ops alarm email notification |
| SSM Parameter Store | Secrets (jwt-secret-key, telegram-bot-token, koreaexim-authkey) |
| IAM | Least-privilege role per Lambda |

---

## Design Patterns

### Layered Architecture

```
HTTP Request
    ↓
Router (api/v1/)     — parse input, call service, return response
    ↓
Service (services/)  — business logic, orchestration
    ↓
Repository (infrastructure/persistence/)  — DynamoDB access only
    ↓
Domain (domain/)     — entities + repository interfaces (protocols)
```

- Routes never call DynamoDB directly — always through the repository layer
- Services raise domain exceptions (`AlertNotFoundError`, etc.) — routes map them to `HTTPException`

**Why this layering:** If DynamoDB is replaced (e.g., with PostgreSQL), only the
`infrastructure/persistence/` layer changes. Services and routes are untouched because
they depend on Protocol interfaces, not concrete implementations.

### Dependency Injection

FastAPI DI chain (all in `core/dependencies.py`):
- `get_current_user` — JWT decode → user lookup
- `get_alert_repository` / `get_user_repository` / etc. — DynamoDB clients
- `get_alert_service(repo=Depends(...))` — injects repo into service
- `get_notification_service` — returns `TelegramNotificationService`

### Repository Protocol Pattern

`domain/repositories.py` defines `Protocol` interfaces (e.g., `IAlertRepository`).
`infrastructure/persistence/dynamodb_alert_repository.py` implements them.
Tests inject moto-backed fakes — no mocking framework needed.

**Why Protocol (not ABC):** DynamoDB repositories don't need to inherit from a base
class — they just need to implement the same method signatures. Protocol avoids
inheritance coupling and makes moto-backed test fixtures naturally compatible
without adapter classes.

---

## DynamoDB Tables

### `{env}-users`
```
PK: user_id
Attrs: email, password_hash (nullable), auth_provider ("local"|"google"),
       google_id (sparse), telegram_chat_id, refresh_token_hash, created_at, updated_at
GSI: email-index
GSI: google-index (sparse — only Google users)
```

### `{env}-currency-alerts`
```
PK: user_id | SK: alert_id
Attrs: currency, direction, target_rate, label, is_active,
       active_user_id (sparse), idempotency_key, created_at, updated_at
GSI: active-user-id-index (sparse — only active alerts)
```

Sparse GSI design: `active_user_id` is set only when `is_active=True`, so the GSI
contains only active alerts. Queries for "all active alerts for a user" hit the index
directly — no table scans, no filter expressions.

### `{env}-exchange-rates`
```
PK: currency
Attrs: rate, buy_rate, sell_rate, spread, date, source, ttl (25h)
```

### `{env}-rate-history`
```
PK: currency | SK: date (YYYY-MM-DD)
Attrs: rate, buy_rate, sell_rate, spread, source
```

### `{env}-notification-history`
```
PK: user_id | SK: triggered_at#alert_id
Attrs: alert_id, currency, target_rate, actual_rate, direction, channel, triggered_at, ttl (90d)
GSI: currency-index
```

**Why composite SK (`triggered_at#alert_id`):** ISO timestamps sort lexicographically,
giving chronological ordering by default. Appending `alert_id` ensures uniqueness —
the same alert could theoretically trigger twice at the same second.

---

## Authentication & Authorization

- **Local auth**: bcrypt password hashing (passlib). JWT access token (15 min) + refresh token (7d)
- **Refresh token storage**: bcrypt hash stored in DynamoDB — not plaintext, not reversible
- **Google OAuth**: `authlib` validates `id_token` with Google public keys. `GET /auth/google` redirects; `GET /auth/google/callback` issues tokens
- **Rate limiting**: `slowapi` — login 5/min, register 3/min → 429 + Retry-After
- **Idempotency**: `POST /alerts` requires `Idempotency-Key` header. Key + response cached in DDB for 5 minutes

**Why DynamoDB for refresh tokens (not Redis):** This is a pure serverless stack.
Adding ElastiCache requires VPC, NAT Gateway, and ongoing operational overhead —
disproportionate cost for a single token lookup. DynamoDB is already in the stack
and supports TTL natively.

**Why bcrypt hash (not plaintext):** A leaked DynamoDB backup should not grant
session access. Hashing refresh tokens follows the same principle as hashing passwords.

---

## Scoring Engine

See [scoring-engine.md](scoring-engine.md) for full technical reference.

**Direction assumption:** user is sending foreign currency → receiving KRW. Higher rate = more KRW = favorable.

**Pipeline:**
```
Rate History (90d) + Current Rate
    ↓ features.py  — percentile, z_score, ma7, ma30, ma_slope, vol_ratio, spread_ratio
    ↓ signals.py   — value_score (0-100), trend_score (0-100), risk_score (0-100)
    ↓ guardrails.py — hard overrides before final score
    ↓ scorer.py    — raw = 0.5v + 0.3t - 0.4r; final = (raw+40)/120×100; label + confidence
    ↓ explainer.py — 2-4 English explanation sentences
```

**Data guards** (run before scoring):
- 0 records → 503 Service Unavailable
- < 7 records → 503 Service Unavailable
- 7–29 records → 200, `confidence=LOW`, `data_warning` field
- Stale > 2 days → 200, `data_warning` field

503 (not 422) is intentional — missing history is a server-side data availability problem, not a client input error.

---

## Event-Driven Architecture

### Flow

```
fetch_rates (Schedule) → "RatesFetched" event → check_alerts (Rule)
                                                    └── on failure → SQS DLQ → dlq_handler
weekly_report (Schedule, Monday 9AM KST)
```

### Why Event-Driven for the Batch Layer

The batch/notification pipeline uses EventBridge pub/sub instead of direct
Lambda invocation (`lambda:Invoke`) for three reasons:

1. **Failure isolation** — fetch_rates and check_alerts have independent failure
   domains. A Telegram API timeout in check_alerts does not cause rate fetching
   to retry or fail. Each Lambda succeeds or fails on its own terms.

2. **Extensibility without producer changes** — the event bus allows future
   subscribers (e.g., a rate analytics consumer, a Slack notifier) without
   modifying fetch_rates. The producer publishes one event; routing is the
   bus's responsibility.

3. **Guaranteed failure capture** — SQS DLQ + dlq_handler ensures zero silent
   drops. If check_alerts fails for any reason, the failed event is preserved
   and logged without any code changes to the producer.

The REST API layer remains synchronous request-response — clients need immediate
answers, and there is no downstream consumer to decouple from.

---

## IAM — Per-Lambda Least Privilege

| Lambda | DynamoDB Access | Other |
|---|---|---|
| FastAPI | CRUD on all 5 tables | SSM read |
| fetch_rates | CRUD on exchange-rates + rate-history | SSM read |
| check_alerts | CRUD on alerts + users + notification-history + exchange-rates | SSM read |
| dlq_handler | None | CloudWatch Logs write only |
| weekly_report | Read on exchange-rates + rate-history | SSM read |

---

## Environment Isolation

All resource names use `{env}-` prefix via SAM Mappings (`dev-` / `prod-`):
- DynamoDB tables: `dev-currency-alerts`, `prod-currency-alerts`, etc.
- EventBridge bus: `dev-currency-events`, `prod-currency-events`
- CloudWatch Dashboard: `dev-currency-tracker`, `prod-currency-tracker`

**Why SAM Mappings (not scattered `!If` conditions):** Centralizes the env→prefix
lookup in one place. Adding a new environment requires one Mappings entry, not
hunting through 20+ resource definitions.

Production-only features (via SAM Conditions):
- DynamoDB PITR enabled
- DynamoDB DeletionProtection enabled

---

## CI/CD

```
Push to main → CI (ci.yml)
  1. ruff check src/ tests/
  2. pytest -v (142 tests, moto mocks)

CI passes → CD (cd.yml, workflow_run trigger)
  deploy-dev:  sam build + sam deploy --stack-name currency-tracker-dev
  deploy-prod: sam build + sam deploy --stack-name currency-tracker-prod
               (requires GitHub environment "production" approval)
```

Each deploy job runs `sam build` independently — no cross-workflow artifact sharing.
GitHub Actions `workflow_run` creates a separate workflow run from CI, so
`actions/download-artifact` cannot access CI's artifacts. Direct build per job
is simpler and avoids cross-workflow coupling.

---

## Testing

142 tests total across 7 test files + 1 test directory:

| File | Coverage |
|---|---|
| `test_api_endpoints.py` | All HTTP endpoints (happy path + error cases) |
| `test_functions.py` | fetch_rates, check_alerts, dlq_handler Lambda handlers |
| `test_repositories.py` | DynamoDB repository implementations (moto) |
| `test_services.py` | Business logic: AlertService, UserService, RateService |
| `test_security.py` | JWT, bcrypt, OAuth token handling |
| `test_scoring/` (75 tests) | features, signals, guardrails, scorer pipeline |

Test strategy:
- `moto` for DynamoDB mocking — real DynamoDB API semantics without AWS calls
- FastAPI `TestClient` + dependency overrides for route-level tests
- `conftest.py` creates per-function DynamoDB tables with all required GSIs

---

## Intentional Design Decisions

**No bulk recommendations endpoint** — `GET /recommendations/{currency}` only (no `/recommendations` for all 4 at once). Each call loads 90 days of history and runs the full pipeline; a bulk endpoint adds asyncio.gather complexity with no UX benefit for a backend-only API.

**503 for data guards** — insufficient or stale rate history returns 503 (not 422). The client sent a valid request; the server lacks the data to answer it.

**Sparse GSI** — `active_user_id` attribute only exists on active alerts. The index therefore contains only active alerts, making "get all active alerts for user" an efficient index query with no scan or filter.

**No Mangum conditional import** — Mangum is always used. The application is Lambda-only; there is no local execution path that bypasses the adapter.

**Pure serverless** — no EC2, VPC, NAT Gateway, ALB, or CodeDeploy. Lambda + DynamoDB + EventBridge covers the entire workload profile (sporadic API traffic, daily batch jobs, event-driven alert checks).
