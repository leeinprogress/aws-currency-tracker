from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AlertValidators:
    @staticmethod
    def validate_currency(v: str) -> str:
        if not v.isalpha():
            raise ValueError("Currency code must contain only letters")
        return v.upper()
    
    @staticmethod
    def validate_condition(v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v_lower = v.lower()
        if v_lower not in ['above', 'below']:
            raise ValueError("Condition must be 'above' or 'below'")
        return v_lower
    
    @staticmethod
    def validate_rate_type(v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v_upper = v.upper()
        if v_upper not in ['TTS', 'TTB', 'DEAL_BAS_R']:
            raise ValueError("Rate type must be 'TTS', 'TTB', or 'DEAL_BAS_R'")
        return v_upper


class AlertCreate(BaseModel):
    user_id: Optional[str] = Field(None)
    telegram_chat_id: Optional[str] = Field(None)
    idempotency_key: Optional[str] = Field(None)
    target_currency: str = Field(..., min_length=3, max_length=3)
    target_rate: float = Field(..., gt=0)
    condition: str = Field(...)
    rate_type: str = Field(default="TTS")
    
    @field_validator('target_currency')
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return AlertValidators.validate_currency(v)
    
    @field_validator('condition')
    @classmethod
    def validate_condition(cls, v: str) -> str:
        return AlertValidators.validate_condition(v)
    
    @field_validator('rate_type')
    @classmethod
    def validate_rate_type(cls, v: str) -> str:
        return AlertValidators.validate_rate_type(v)


class AlertUpdate(BaseModel):
    target_rate: Optional[float] = Field(None, gt=0)
    condition: Optional[str] = Field(None)
    rate_type: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)
    
    @field_validator('condition')
    @classmethod
    def validate_condition(cls, v: Optional[str]) -> Optional[str]:
        return AlertValidators.validate_condition(v)
    
    @field_validator('rate_type')
    @classmethod
    def validate_rate_type(cls, v: Optional[str]) -> Optional[str]:
        return AlertValidators.validate_rate_type(v)


class AlertResponse(BaseModel):
    alert_id: str
    user_id: str
    telegram_chat_id: str
    target_currency: str
    target_rate: float
    condition: str
    rate_type: str
    is_active: bool
    idempotency_key: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class AlertListResponse(BaseModel):
    alerts: list[AlertResponse]
    total: int


class MessageResponse(BaseModel):
    message: str
