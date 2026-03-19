# AWS Currency Tracker

> Serverless backend for monitoring KRW exchange rates and optimizing remittance timing.

## Architecture

```
Client (Postman / Swagger UI)
    | HTTPS
[API Gateway] -> proxy to Lambda
    |
[FastAPI Lambda - Mangum adapter]
    |-- /api/v1/auth/*
    |-- /api/v1/alerts/*
    |-- /api/v1/rates/*
    |-- /api/v1/users/*
    |-- /api/v1/notifications/*
    |-- /api/v1/recommendations/*
    +-- /health
    |
[DynamoDB - 5 tables]

[Lambda - Scheduled Jobs]
fetch_rates      <- EventBridge Schedule (daily 11AM KST)
    | publishes "Rate Updated" event
check_alerts     <- EventBridge Rule
    +-- on failure -> [SQS DLQ] -> dlq_handler Lambda -> CloudWatch Logs
weekly_report    <- EventBridge Schedule (every Monday 9AM KST)

[CI/CD]
GitHub Actions -> sam build -> sam deploy (development / production)
```

## AWS Services

| Service | Purpose |
|---|---|
| Lambda (x5) | FastAPI API + fetch_rates + check_alerts + dlq_handler + weekly_report |
| API Gateway | HTTPS entry point, Lambda proxy integration |
| DynamoDB (5 tables) | Alerts, Users, Exchange Rates, Rate History, Notification History |
| EventBridge | Scheduled triggers + event routing (per-env custom bus) |
| SQS | Dead Letter Queue for check_alerts failures |
| SSM Parameter Store | Secrets (SecureString, resolved at deploy time) |
| CloudWatch | Logs + 7 Alarms + Dashboard |
| SNS | Ops alarm notifications (email) |
| IAM | Least-privilege roles per Lambda |

## API Endpoints

All endpoints prefixed with `/api/v1/`. Swagger UI available at `/docs`.

### Auth
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | No | Register new user |
| POST | `/auth/login` | No | Login, returns JWT access + refresh tokens |
| POST | `/auth/refresh` | No | Refresh access token |
| POST | `/auth/logout` | Yes | Invalidate refresh token |
| GET | `/auth/google` | No | Google OAuth redirect |
| GET | `/auth/google/callback` | No | Google OAuth callback |

### Users
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/users/me` | Yes | Get current user profile |
| PUT | `/users/me` | Yes | Update profile (telegram_chat_id) |
| DELETE | `/users/me` | Yes | Delete account + cascade alerts |

### Alerts
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/alerts` | Yes | Create alert (Idempotency-Key required) |
| GET | `/alerts` | Yes | List user's alerts |
| GET | `/alerts/{id}` | Yes | Get specific alert |
| PUT | `/alerts/{id}` | Yes | Update alert |
| DELETE | `/alerts/{id}` | Yes | Delete alert |
| PUT | `/alerts/{id}/toggle` | Yes | Toggle alert on/off |

### Rates
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/rates` | Yes | Get all current rates |
| GET | `/rates/{currency}` | Yes | Get specific currency rate |
| GET | `/rates/{currency}/history` | Yes | Historical rates (up to 90 days) |
| GET | `/rates/{currency}/analysis` | Yes | Statistical analysis (MA, percentile, z-score) |

### Recommendations
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/recommendations/{currency}` | Yes | Scoring engine recommendation |

### Notifications
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/notifications` | Yes | Paginated notification history |

### Health
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | `{"status": "ok", "environment": "...", "version": "1.0.0"}` |

## Local Setup

```bash
git clone https://github.com/leeinprogress/aws-currency-tracker.git
cd aws-currency-tracker
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # fill in values
make check             # lint + test
```

## Testing

```bash
# Run all tests (142 tests)
make test

# Lint
make lint

# Both (same as CI)
make check
```

## Deployment

```bash
# 1. Create SSM parameters (one-time setup)
aws ssm put-parameter --name /currency-tracker/development/jwt-secret-key \
  --value "your-secret" --type SecureString
aws ssm put-parameter --name /currency-tracker/development/telegram-bot-token \
  --value "your-token" --type SecureString
aws ssm put-parameter --name /currency-tracker/development/koreaexim-authkey \
  --value "your-key" --type SecureString

# 2. Validate and build
make validate
make build

# 3. Deploy
sam deploy --stack-name currency-tracker-dev \
  --parameter-overrides Environment=development OpsEmail=your@email.com \
  --no-confirm-changeset --no-fail-on-empty-changeset
```

## Project Structure

```
src/
|-- app/
|   |-- api/v1/           # FastAPI routers (auth, alerts, rates, users, notifications, recommendations)
|   |-- clients/           # External API clients (Korea Exim Bank)
|   |-- core/              # Config, security, dependencies, exceptions
|   |-- domain/            # Entities, repository interfaces, notification ABC
|   |-- infrastructure/    # DynamoDB repositories, Telegram service, logging
|   |-- schemas/           # Pydantic request/response models
|   |-- services/          # Business logic + scoring engine
|   +-- main.py            # FastAPI app entry + Mangum handler
|-- functions/
|   |-- fetch_rates.py     # Scheduled rate collection (daily)
|   |-- check_alerts.py    # Event-driven alert evaluation
|   |-- weekly_report.py   # Weekly Telegram summary (Monday)
|   +-- dlq_handler.py     # Logs failed events from DLQ
tests/
|-- test_api_endpoints.py
|-- test_functions.py
|-- test_repositories.py
|-- test_services.py
|-- test_security.py
+-- test_scoring/          # 75 scoring engine tests
template.yaml              # AWS SAM infrastructure
```

## Key Design Decisions

- **Pure serverless**: Lambda + DynamoDB + EventBridge. No EC2, VPC, or ALB.
- **Event-driven decoupling**: fetch_rates publishes to EventBridge, check_alerts subscribes. Failure isolation + DLQ safety net.
- **Sparse GSI**: `active_user_id-index` on AlertsTable — only active alerts in the index, efficient queries.
- **503 for data guards**: Missing rate history returns 503 (server-side data availability problem), not 422.
- **Per-Lambda IAM**: Each Lambda has only the DynamoDB policies it needs.
- **Environment isolation**: `dev-`/`prod-` prefix on all resources via SAM Mappings. PITR + DeletionProtection production-only.

## Scoring Engine

See [DOCS/scoring-engine.md](DOCS/scoring-engine.md) for the full technical reference.

The engine evaluates remittance timing for Korean expats receiving KRW:
- **Pipeline**: features -> signals -> guardrails -> scorer -> explainer
- **Labels**: FAVORABLE (>= 70) / NEUTRAL (40-69) / WAIT (< 40) / CAUTION (guardrail override)
- **Confidence**: HIGH / MEDIUM / LOW based on risk score

