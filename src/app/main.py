from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1 import alerts, auth, notifications, rates, recommendations, users
from app.core.config import settings
from app.core.exceptions import (
    AlertNotFoundError,
    DuplicateAlertError,
    InsufficientDataError,
    InvalidCredentialsError,
    RateNotFoundError,
    ScoringUnavailableError,
    UserNotFoundError,
)
from app.infrastructure.logging.logger import get_logger, setup_logging
from app.infrastructure.logging.middleware import RequestLoggingMiddleware

setup_logging(level="INFO")
logger = get_logger(__name__)

# Rate limiter (shared instance used by auth routes)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Currency tracking and alert system with Telegram notifications",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Domain exception → HTTP response mapping
# ---------------------------------------------------------------------------

@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(request: Request, exc: UserNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": "User not found", "code": "USER_NOT_FOUND"})


@app.exception_handler(AlertNotFoundError)
async def alert_not_found_handler(request: Request, exc: AlertNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": "Alert not found", "code": "ALERT_NOT_FOUND"})


@app.exception_handler(DuplicateAlertError)
async def duplicate_alert_handler(request: Request, exc: DuplicateAlertError) -> JSONResponse:
    return JSONResponse(
        status_code=409, content={"error": "Alert already exists", "code": "DUPLICATE_ALERT"}
    )


@app.exception_handler(InvalidCredentialsError)
async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError) -> JSONResponse:
    return JSONResponse(
        status_code=401, content={"error": "Invalid credentials", "code": "INVALID_CREDENTIALS"}
    )


@app.exception_handler(RateNotFoundError)
async def rate_not_found_handler(request: Request, exc: RateNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404, content={"error": "Exchange rate not found", "code": "RATE_NOT_FOUND"}
    )


@app.exception_handler(ScoringUnavailableError)
async def scoring_unavailable_handler(
    request: Request, exc: ScoringUnavailableError
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": "Recommendation service is warming up — no rate data available yet.",
            "code": "SERVICE_WARMING_UP",
            "trading_days_available": 0,
            "trading_days_required": 7,
            "trading_days_until_ready": 7,
        },
    )


@app.exception_handler(InsufficientDataError)
async def insufficient_data_handler(
    request: Request, exc: InsufficientDataError
) -> JSONResponse:
    days_until_ready = exc.min_required - exc.actual
    return JSONResponse(
        status_code=503,
        content={
            "error": (
                f"Recommendation service is warming up — "
                f"{days_until_ready} more trading day(s) of rate data needed."
            ),
            "code": "SERVICE_WARMING_UP",
            "trading_days_available": exc.actual,
            "trading_days_required": exc.min_required,
            "trading_days_until_ready": days_until_ready,
        },
    )


logger.info("application_initialized", version=settings.VERSION)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["alerts"])
app.include_router(rates.router, prefix="/api/v1/rates", tags=["rates"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["notifications"])
app.include_router(
    recommendations.router, prefix="/api/v1/recommendations", tags=["recommendations"]
)


@app.get("/")
async def root():
    return {
        "message": "Currency Alert API",
        "version": settings.VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
    }


handler = Mangum(app)
