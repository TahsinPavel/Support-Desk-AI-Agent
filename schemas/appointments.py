from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID


# ==========================================
# Response Models
# ==========================================

class AppointmentResponse(BaseModel):
    """Single appointment response."""
    id: str
    customer_name: Optional[str] = None
    customer_contact: Optional[str] = None
    service: Optional[str] = None
    requested_time: Optional[datetime] = None
    confirmed_time: Optional[datetime] = None
    status: str
    notes: Optional[str] = None
    ai_conversation: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppointmentListResponse(BaseModel):
    """List of appointments."""
    appointments: List[AppointmentResponse]
    total: int


class TrendItem(BaseModel):
    """Single day appointment count for trend."""
    date: str  # YYYY-MM-DD
    count: int


class AppointmentSummaryResponse(BaseModel):
    """Appointment summary statistics."""
    total: int
    pending: int
    confirmed: int
    completed: int
    canceled: int
    trend: List[TrendItem]


# ==========================================
# Request Models
# ==========================================

class AppointmentCreate(BaseModel):
    """Request body for creating appointment."""
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_contact: str = Field(..., min_length=1, max_length=255)
    service: Optional[str] = Field(None, max_length=255)
    requested_time: Optional[datetime] = None
    confirmed_time: Optional[datetime] = None
    status: Optional[str] = Field("pending", pattern="^(pending|confirmed|completed|canceled)$")
    notes: Optional[str] = None


class AppointmentUpdate(BaseModel):
    """Request body for updating appointment."""
    customer_name: Optional[str] = Field(None, max_length=255)
    customer_contact: Optional[str] = Field(None, max_length=255)
    service: Optional[str] = Field(None, max_length=255)
    requested_time: Optional[datetime] = None
    confirmed_time: Optional[datetime] = None
    status: Optional[str] = Field(None, pattern="^(pending|confirmed|completed|canceled)$")
    notes: Optional[str] = None

