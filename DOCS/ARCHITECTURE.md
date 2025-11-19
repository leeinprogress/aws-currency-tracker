# Architecture & Design Decisions

This document outlines the architecture and key design decisions for the Currency Alert System. It's a serverless application built on AWS using FastAPI, Lambda, and DynamoDB.

## Project Structure

The application follows a clean, modular structure that separates concerns and makes the codebase maintainable:

```
src/
├── app/                    # FastAPI application (shared code)
│   ├── main.py            # Application entry point
│   ├── api/               # API routes
│   │   └── v1/
│   │       ├── alerts.py  # Alert endpoints
│   │       └── auth.py    # Authentication endpoints
│   ├── core/              # Core functionality
│   │   ├── config.py      # Configuration management
│   │   ├── dependencies.py # FastAPI dependency injection
│   │   └── security.py    # JWT and password hashing
│   ├── db/                # Database layer
│   │   ├── models/        # Domain models
│   │   │   ├── alert.py
│   │   │   └── user.py
│   │   └── repositories/ # Data access layer
│   │       ├── alert_repository.py
│   │       └── user_repository.py
│   ├── schemas/           # Pydantic schemas (request/response)
│   │   ├── alert.py
│   │   └── user.py
│   ├── services/          # Business logic layer
│   │   ├── alert_service.py
│   │   └── user_service.py
│   └── clients/           # External API clients
│       └── exchange_rate_client.py
└── functions/             # Lambda functions
    ├── fetch_rates.py     # Fetches rates from KoreaExim API
    └── check_alerts.py    # Checks alerts and sends notifications
```

## Design Patterns

### Separation of Concerns

The codebase is organized into distinct layers:

- **Routers** (`api/v1/`): Handle HTTP requests and responses, validate input, call services
- **Services** (`services/`): Contain business logic, orchestrate operations
- **Repositories** (`db/repositories/`): Handle data access, abstract database operations
- **Models** (`db/models/`): Domain entities, database-agnostic
- **Schemas** (`schemas/`): API contracts, request/response validation using Pydantic

This separation makes the code easier to test, maintain, and extend.

### Dependency Injection

FastAPI's dependency injection system is used throughout:

- Repositories are injected via dependencies, making it easy to swap implementations
- Authentication is handled through dependencies (`get_current_user`)
- Services are created via dependencies, ensuring proper initialization

### Repository Pattern

The repository pattern abstracts data access:

- `AlertRepository` protocol defines the interface
- `DynamoDBAlertRepository` provides the concrete implementation
- Easy to add other implementations (PostgreSQL, Redis) without changing business logic

### API Versioning

Routes are organized under `/api/v1/` to allow for future API versions without breaking existing clients.

## AWS Architecture

### Components

1. **API Gateway + Lambda (FastAPI)**
   - Handles all HTTP requests
   - FastAPI app wrapped with Mangum for Lambda compatibility
   - Auto-generated OpenAPI docs at `/docs`

2. **DynamoDB Tables**
   - `currency-alerts`: Stores user alerts
   - `users`: Stores user accounts and authentication data
   - Both use pay-per-request billing

3. **Lambda Functions**
   - `FetchRatesFunction`: Runs every 5 minutes, fetches rates from KoreaExim API
   - `CheckAlertsFunction`: Triggered by EventBridge when rates are updated

4. **EventBridge**
   - Custom event bus: `currency-events`
   - `FetchRatesFunction` publishes rate update events
   - `RateUpdateRule` routes events to `CheckAlertsFunction`

### Data Flow

1. User creates an alert via API → Stored in DynamoDB
2. Every 5 minutes: `FetchRatesFunction` runs
   - Queries DynamoDB for active alerts
   - Fetches current rates from KoreaExim API
   - Publishes rate update event to EventBridge
3. EventBridge triggers `CheckAlertsFunction`
   - Queries DynamoDB for active alerts matching the base currency
   - Compares current rates with alert conditions
   - Sends Telegram notifications for triggered alerts

## Authentication & Authorization

The system uses JWT-based authentication:

- Users register with email, password, and Telegram chat ID
- Passwords are hashed using bcrypt
- Login returns a JWT access token (30-minute expiry by default)
- All alert endpoints require Bearer token authentication
- Users can only access their own alerts (enforced at the service layer)

## Exchange Rate API

The system uses the KoreaExim API for exchange rates:

- Base currency is always KRW (Korean Won)
- Supports multiple rate types: TTS (selling), TTB (buying), DEAL_BAS_R (deal base rate)
- Rates are fetched daily and cached in EventBridge events

## Error Handling

- **API Layer**: FastAPI HTTPException with appropriate status codes
- **Service Layer**: Business logic errors, validation
- **Repository Layer**: Database-specific errors, graceful fallbacks
- **Lambda Functions**: Try-catch with CloudWatch logging

## Configuration

Configuration is managed through environment variables and Pydantic Settings:

- Type-safe configuration with validation
- Sensible defaults where appropriate
- Secrets managed via SAM template parameters

## Testing

The architecture supports testing at multiple levels:

- **Unit Tests**: Mock repositories, test services in isolation
- **Integration Tests**: Use test DynamoDB tables
- **API Tests**: FastAPI TestClient for endpoint testing
- **Lambda Tests**: Local testing with SAM CLI or pytest

## Future Enhancements

Potential improvements and features:

- Add rate limiting to prevent abuse
- Implement refresh tokens for longer sessions
- Add caching layer for frequently accessed data
- Support for multiple exchange rate providers
- WebSocket support for real-time rate updates
- Background task queue for heavy operations
- Metrics and monitoring dashboards
