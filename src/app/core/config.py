"""
Application configuration
"""
import os
from typing import List

try:
    from pydantic_settings import BaseSettings
    from pydantic import ConfigDict
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings, ConfigDict


class Settings(BaseSettings):
    """Application settings"""
    
    PROJECT_NAME: str = "Currency Alert API"
    VERSION: str = "1.0.0"
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]
    
    # DynamoDB settings
    ALERTS_TABLE_NAME: str
    USERS_TABLE_NAME: str
    AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    
    # KoreaExim Exchange Rate API
    KOREAEXIM_AUTHKEY: str = os.environ.get("KOREAEXIM_AUTHKEY", "")
    
    # Legacy Exchange API (not used, kept for compatibility)
    EXCHANGE_API_KEY: str = os.environ.get("EXCHANGE_API_KEY", "")
    EXCHANGE_API_URL: str = os.environ.get(
        "EXCHANGE_API_URL", "https://oapi.koreaexim.go.kr/site/program/financial/exchangeJSON"
    )
    
    # EventBridge
    EVENTBRIDGE_BUS: str = os.environ.get("EVENTBRIDGE_BUS", "currency-events")
    
    # Security
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    model_config = ConfigDict(case_sensitive=True)


settings = Settings()

