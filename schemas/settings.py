from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
import uuid


ChannelType = Literal["sms", "email", "chat", "voice"]


class SettingsChannelResponse(BaseModel):
    id: uuid.UUID
    type: ChannelType
    identifier: str
    status: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class TenantSettingsResponse(BaseModel):
    id: uuid.UUID

    # Business / account
    business_name: str
    email: str
    primary_phone: Optional[str] = None
    timezone: str

    # Business hours
    open_time: Optional[str] = None
    close_time: Optional[str] = None

    # AI settings
    ai_provider: str
    ai_system_prompt: Optional[str] = None
    escalation_phone: Optional[str] = None

    # Subscription (read-only for settings page)
    plan: str
    subscription_status: str

    # Metadata
    onboarding_completed: bool
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Channels
    channels: List[SettingsChannelResponse]


class TenantSettingsUpdateRequest(BaseModel):
    # NOTE: email/password/faqs/services are intentionally NOT here (separate routes)

    business_name: Optional[str] = Field(None, min_length=1, max_length=255)
    primary_phone: Optional[str] = Field(None, max_length=50)
    timezone: Optional[str] = Field(None, max_length=50)

    open_time: Optional[str] = Field(None, max_length=10, description="e.g. 09:00")
    close_time: Optional[str] = Field(None, max_length=10, description="e.g. 17:00")

    ai_provider: Optional[str] = Field(None, max_length=50)
    ai_system_prompt: Optional[str] = None
    escalation_phone: Optional[str] = Field(None, max_length=50)
