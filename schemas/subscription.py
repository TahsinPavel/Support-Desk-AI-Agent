from pydantic import BaseModel, Field
from typing import Optional, Literal, Any, Dict
from datetime import datetime


# ==========================================
# Request Models
# ==========================================

class ActivateSubscriptionRequest(BaseModel):
    """Request body for activating a subscription."""
    email: str = Field(..., description="Tenant email address")
    paddle_customer_id: str = Field(..., description="Paddle customer ID")
    paddle_subscription_id: str = Field(..., description="Paddle subscription ID")
    plan: Literal["starter", "growth", "enterprise"] = Field("starter", description="Subscription plan")


# ==========================================
# Response Models
# ==========================================

class ActivateSubscriptionResponse(BaseModel):
    """Response after activating subscription."""
    success: bool
    message: str
    tenant_id: str
    plan: str


class WebhookResponse(BaseModel):
    """Response for webhook acknowledgement."""
    success: bool
    message: str


# ==========================================
# Paddle Webhook Event Models
# ==========================================

class PaddleEventData(BaseModel):
    """Paddle event data structure."""
    id: Optional[str] = None
    customer_id: Optional[str] = None
    status: Optional[str] = None
    custom_data: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"  # Allow additional fields from Paddle


class PaddleWebhookEvent(BaseModel):
    """Paddle webhook event structure."""
    event_type: str
    event_id: Optional[str] = None
    occurred_at: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"  # Allow additional fields from Paddle

