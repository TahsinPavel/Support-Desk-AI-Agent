from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID


# ==========================================
# Response Models
# ==========================================

class SMSMessageResponse(BaseModel):
    """Single SMS message response."""
    id: str
    customer_contact: str
    message_text: Optional[str] = None
    direction: Literal["incoming", "outgoing"]
    created_at: datetime
    ai_response: Optional[str] = None

    class Config:
        from_attributes = True


class SMSMessageListResponse(BaseModel):
    """List of SMS messages."""
    messages: list[SMSMessageResponse]
    total: int


# ==========================================
# Request Models
# ==========================================

class SendSMSRequest(BaseModel):
    """Request body for sending SMS."""
    channel_id: UUID = Field(..., description="UUID of the SMS channel to send from")
    to: str = Field(..., description="Recipient phone number (E.164 format)", example="+15551234567")
    message_text: str = Field(..., description="Message content to send", min_length=1, max_length=1600)


class SendSMSResponse(BaseModel):
    """Response after sending SMS."""
    success: bool
    message_id: str
    status: str
    to: str
    message_text: str
    twilio_sid: Optional[str] = None

