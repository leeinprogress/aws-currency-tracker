# AWS Currency Tracking & Alert Platform

A serverless currency alert service that notifies users via Telegram when exchange rates hit their target. Built with AWS Lambda, DynamoDB, EventBridge, and FastAPI to demonstrate production-ready patterns in a compact, real-world application.

## What It Does

- **Set alerts**: "Notify me when USD drops below 1,340 KRW"
- **Get notified**: Receive Telegram messages when conditions are met
- **Track rates**: View current exchange rates and historical trends
- **Manage multiple alerts**: Create unlimited alerts for different currencies and targets

## Tech Stack

| Category | Technologies |
|----------|--------------|
| Language & Framework | Python 3.11+, FastAPI, Mangum |
| AWS Services | Lambda, API Gateway, EventBridge, DynamoDB |
| Infrastructure | AWS SAM (`template.yaml`) |
| External APIs | Korea Exim Bank (daily rates), Telegram Bot API |
| Testing | pytest, moto (AWS mocking) |
| Tooling | ruff (linting), structlog (JSON logging), GitHub Actions |

## Architecture

The platform follows a "thin API, rich event pipeline" model. FastAPI focuses on CRUD + authentication, while background Lambdas handle periodic rate ingestion and alert fan-out through EventBridge. DynamoDB provides low-latency persistence for both alerts and user metadata.


### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login and get JWT token |

### Alerts
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/alerts` | Create new alert |
| GET | `/api/v1/alerts` | List user's alerts |
| GET | `/api/v1/alerts/{id}` | Get specific alert |
| PUT | `/api/v1/alerts/{id}` | Update alert |
| DELETE | `/api/v1/alerts/{id}` | Delete alert |
| PUT | `/api/v1/alerts/{id}/toggle` | Toggle alert on/off |

### Exchange Rates
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/rates` | Get all current rates |
| GET | `/api/v1/rates/{currency}` | Get specific currency rate |
| GET | `/api/v1/rates/{currency}/history` | Get historical rates (up to 90 days) |

## DynamoDB Patterns

This project demonstrates production-ready DynamoDB patterns:

| Pattern | Purpose | Implementation |
|---------|---------|----------------|
| **Conditional Writes** | Prevent duplicate alerts | `ConditionExpression` on save |
| **Sparse GSI** | Efficient active alert queries | `active_user_id` index (only active items) |
| **TTL** | Auto-expire cached rates | `ttl` attribute on rate cache |
| **Single Table Design** | Reduced latency | Alerts, Users in optimized structure |

## Local Setup

```bash
git clone https://github.com/leeinprogress/aws-currency-tracker.git
cd aws-currency-tracker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

```bash
# Required
KOREAEXIM_AUTHKEY=your_api_key      # From Korea Exim Bank
TELEGRAM_BOT_TOKEN=your_bot_token    # From @BotFather
SECRET_KEY=your_jwt_secret           # For JWT signing

# AWS (auto-set in Lambda)
ALERTS_TABLE_NAME=currency-alerts
USERS_TABLE_NAME=users
EXCHANGE_RATES_TABLE_NAME=exchange-rates
RATE_HISTORY_TABLE_NAME=rate-history
```

## Telegram Bot Setup

1. **Create Bot**: Message [@BotFather](https://t.me/BotFather) → `/newbot`
2. **Get Chat ID**: 
   - Send any message to your bot
   - Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Find `"chat":{"id":123456789}`
3. **Register**: Include `telegram_chat_id` when creating user account

## Testing

```bash
# Run all tests (46 tests)
pytest

# Verbose output
pytest -v

# Specific test file
pytest tests/test_repositories.py
```

**Test Coverage:**
- Repository layer (CRUD, conditional writes, sparse GSI)
- Lambda functions (rate fetching, alert evaluation)
- API endpoints (auth, alerts, rates)
- Rate history tracking

## Deployment

```bash
sam build
sam deploy --guided
```

SAM will prompt for:
- `KoreaEximAuthKey` - API key for exchange rates
- `TelegramBotToken` - Bot token for notifications
- `JwtSecretKey` - Secret for JWT signing

## Project Structure

```
src/
├── app/
│   ├── api/v1/           # FastAPI routers (alerts, auth, rates)
│   ├── clients/          # External API clients (Korea Exim)
│   ├── core/             # Config, security, dependencies
│   ├── domain/           # Entities and repository interfaces
│   ├── infrastructure/   # DynamoDB repositories, logging
│   ├── schemas/          # Pydantic models
│   ├── services/         # Business logic
│   └── main.py           # FastAPI app entry
├── functions/
│   ├── fetch_rates.py    # Scheduled rate collection
│   └── check_alerts.py   # Event-driven alert evaluation
tests/
├── test_api_endpoints.py
├── test_functions.py
├── test_repositories.py
├── test_conditional_updates.py
├── test_rate_history.py
└── test_sparse_gsi.py
```

## Data Flow

1. **Daily at 12:00 KST**: `fetch_rates` Lambda runs
2. **Fetches rates** from Korea Exim Bank API
3. **Saves to history** for trend analysis
4. **Publishes event** to EventBridge
5. **`check_alerts`** Lambda receives event
6. **Evaluates all active alerts** against current rates
7. **Sends Telegram** to users with matching conditions

## Limitations

- Exchange rates update **once daily** (11 AM KST from Korea Exim Bank)
- Not suitable for real-time trading
- Free tier API limit: 1,000 calls/day

## CI/CD

GitHub Actions runs on every push:
- Python 3.11 & 3.12 compatibility
- Linting with `ruff`
- Full test suite

---

Feedback welcome. This is my playground for AWS serverless patterns.
