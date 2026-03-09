from typing import List

try:
    from pydantic_settings import BaseSettings
    from pydantic import ConfigDict
except ImportError:
    from pydantic import BaseSettings, ConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Currency Alert API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    ALLOWED_ORIGINS: List[str] = ["*"]

    # DynamoDB
    ALERTS_TABLE_NAME: str
    USERS_TABLE_NAME: str
    EXCHANGE_RATES_TABLE_NAME: str
    RATE_HISTORY_TABLE_NAME: str = "rate-history"
    NOTIFICATION_HISTORY_TABLE_NAME: str = "notification-history"
    AWS_REGION: str = "ap-northeast-2"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""

    # KoreaExim API
    KOREAEXIM_AUTHKEY: str = ""

    # EventBridge
    EVENTBRIDGE_BUS: str = "currency-events"

    # Security
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    model_config = ConfigDict(case_sensitive=True)


settings = Settings()
