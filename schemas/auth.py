from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class TenantSignupRequest(BaseModel):
    owner_name: Optional[str] = None
    business_name: str
    email: str
    password: str
    primary_phone: Optional[str] = None
    timezone: Optional[str] = "UTC"


class TenantLoginRequest(BaseModel):
    email: str
    password: str


class TenantResponse(BaseModel):
    id: uuid.UUID
    owner_name: Optional[str] = None
    business_name: str
    email: str
    primary_phone: Optional[str] = None
    timezone: str
    plan: str
    subscription_status: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None
    tenant: TenantResponse