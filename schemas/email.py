from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from uuid import UUID


# ==========================================
# Response Models
# ==========================================

class EmailMessageResponse(BaseModel):
    """Single email message response."""
    id: str
    subject: Optional[str] = None
    from_email: Optional[str] = None
    to_email: Optional[str] = None
    message_text: Optional[str] = None
    direction: Literal["incoming", "outgoing"]
    ai_response: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EmailMessageListResponse(BaseModel):
    """List of email messages."""
    emails: List[EmailMessageResponse]
    total: int


# ==========================================
# Request Models
# ==========================================

class SendEmailRequest(BaseModel):
    """Request body for sending email."""
    to_email: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line", min_length=1, max_length=500)
    message: str = Field(..., description="Email body text", min_length=1)


class SendEmailResponse(BaseModel):
    """Response after sending email."""
    status: str
    message_id: str


# ==========================================
# Webhook Request (for incoming emails)
# ==========================================

class ReceiveEmailRequest(BaseModel):
    """Request body for receiving email webhook."""
    customer_email: str
    subject: Optional[str] = None
    message: str
    tenant_id: UUID

