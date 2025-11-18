"""
Alert Pydantic schemas for request/response validation
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AlertBase(BaseModel):
    """Base alert schema"""
    user_id: str = Field(..., description="User identifier")
    telegram_chat_id: str = Field(..., description="Telegram chat ID for notifications")
    base_currency: str = Field(..., description="Base currency code (KoreaExim API uses KRW as base, so always KRW)", min_length=3, max_length=3)
    target_currency: str = Field(..., description="Target currency code (e.g., USD, EUR)", min_length=3, max_length=3)
    target_rate: float = Field(..., description="Target exchange rate", gt=0)
    condition: str = Field(..., description="Alert condition: 'above' or 'below'")
    rate_type: str = Field(..., description="Rate type: 'TTS' (Telegraphic Transfer Selling), 'TTB' (Telegraphic Transfer Buying), 'DEAL_BAS_R' (Deal Base Rate)")
    
    @field_validator('base_currency', 'target_currency')
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate and uppercase currency code"""
        if not v.isalpha():
            raise ValueError("Currency code must contain only letters")
        return v.upper()
    
    @field_validator('base_currency')
    @classmethod
    def validate_base_currency(cls, v: str) -> str:
        """KoreaExim API uses KRW as base, so base_currency must always be KRW"""
        v_upper = v.upper()
        if v_upper != "KRW":
            raise ValueError("Base currency must be KRW for KoreaExim API")
        return v_upper
    
    @field_validator('condition')
    @classmethod
    def validate_condition(cls, v: str) -> str:
        """Validate condition"""
        v_lower = v.lower()
        if v_lower not in ['above', 'below']:
            raise ValueError("Condition must be 'above' or 'below'")
        return v_lower
    
    @field_validator('rate_type')
    @classmethod
    def validate_rate_type(cls, v: str) -> str:
        """Validate rate type"""
        v_upper = v.upper()
        if v_upper not in ['TTS', 'TTB', 'DEAL_BAS_R']:
            raise ValueError("Rate type must be 'TTS', 'TTB', or 'DEAL_BAS_R'")
        return v_upper


class AlertCreate(BaseModel):
    """Schema for creating an alert (user metadata is injected server-side)"""
    user_id: Optional[str] = Field(None, description="User identifier")
    telegram_chat_id: Optional[str] = Field(None, description="Telegram chat ID")
    base_currency: str = Field(default="KRW", description="Base currency code (KoreaExim API uses KRW as base, so always KRW)", min_length=3, max_length=3)
    target_currency: str = Field(..., description="Target currency code (e.g., USD, EUR)", min_length=3, max_length=3)
    target_rate: float = Field(..., description="Target exchange rate", gt=0)
    condition: str = Field(..., description="Alert condition: 'above' or 'below'")
    rate_type: str = Field(default="TTS", description="Rate type: 'TTS' (Telegraphic Transfer Selling), 'TTB' (Telegraphic Transfer Buying), 'DEAL_BAS_R' (Deal Base Rate)")
    
    @field_validator('base_currency', 'target_currency')
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate and uppercase currency code"""
        if not v.isalpha():
            raise ValueError("Currency code must contain only letters")
        return v.upper()
    
    @field_validator('base_currency')
    @classmethod
    def validate_base_currency(cls, v: str) -> str:
        """KoreaExim API uses KRW as base, so base_currency must always be KRW"""
        v_upper = v.upper()
        if v_upper != "KRW":
            raise ValueError("Base currency must be KRW for KoreaExim API")
        return v_upper
    
    @field_validator('condition')
    @classmethod
    def validate_condition(cls, v: str) -> str:
        """Validate condition"""
        v_lower = v.lower()
        if v_lower not in ['above', 'below']:
            raise ValueError("Condition must be 'above' or 'below'")
        return v_lower
    
    @field_validator('rate_type')
    @classmethod
    def validate_rate_type(cls, v: str) -> str:
        """Validate rate type"""
        v_upper = v.upper()
        if v_upper not in ['TTS', 'TTB', 'DEAL_BAS_R']:
            raise ValueError("Rate type must be 'TTS', 'TTB', or 'DEAL_BAS_R'")
        return v_upper


class AlertUpdate(BaseModel):
    """Schema for updating an alert"""
    target_rate: Optional[float] = Field(None, description="New target rate", gt=0)
    condition: Optional[str] = Field(None, description="New condition: 'above' or 'below'")
    rate_type: Optional[str] = Field(None, description="Rate type: 'TTS', 'TTB', or 'DEAL_BAS_R'")
    is_active: Optional[bool] = Field(None, description="Active status")
    
    @field_validator('condition')
    @classmethod
    def validate_condition(cls, v: Optional[str]) -> Optional[str]:
        """Validate condition"""
        if v is None:
            return v
        v_lower = v.lower()
        if v_lower not in ['above', 'below']:
            raise ValueError("Condition must be 'above' or 'below'")
        return v_lower
    
    @field_validator('rate_type')
    @classmethod
    def validate_rate_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate rate type"""
        if v is None:
            return v
        v_upper = v.upper()
        if v_upper not in ['TTS', 'TTB', 'DEAL_BAS_R']:
            raise ValueError("Rate type must be 'TTS', 'TTB', or 'DEAL_BAS_R'")
        return v_upper


class AlertResponse(AlertBase):
    """Schema for alert response"""
    alert_id: str = Field(..., description="Unique alert identifier")
    is_active: bool = Field(..., description="Whether the alert is active")
    created_at: Optional[datetime] = Field(None, description="Alert creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Alert last update timestamp")
    
    model_config = ConfigDict(from_attributes=True)


class AlertListResponse(BaseModel):
    """Schema for list of alerts"""
    alerts: list[AlertResponse]
    total: int


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str

