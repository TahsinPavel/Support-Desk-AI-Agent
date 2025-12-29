from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class TenantSignupRequest(BaseModel):
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
    business_name: str
    email: str
    primary_phone: Optional[str] = None
    timezone: str
    plan: str
    subscription_status: str
    onboarding_completed: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None
    tenant: TenantResponse


class GoogleAuthorizeResponse(BaseModel):
    authorization_url: str
    state: str


class GoogleExchangeRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str
    business_name: Optional[str] = None
    primary_phone: Optional[str] = None
    timezone: Optional[str] = "UTC"


class GoogleCredentialRequest(BaseModel):
    credential: str
    business_name: Optional[str] = None
    primary_phone: Optional[str] = None
    timezone: Optional[str] = "UTC"