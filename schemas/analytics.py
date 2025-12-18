from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import date


class MessageOverTimeItem(BaseModel):
    """Single day message count."""
    date: str  # YYYY-MM-DD format
    count: int


class BasicAnalyticsResponse(BaseModel):
    """Basic analytics response for tenant dashboard."""
    total_messages: int
    ai_resolved: int
    escalated: int
    sms_count: int
    email_count: int
    chat_count: int
    voice_count: int
    messages_over_time: List[MessageOverTimeItem]


class DailyCountItem(BaseModel):
    date: str  # YYYY-MM-DD
    count: int


ChannelType = Literal["sms", "email", "chat", "voice"]


class ChannelSummaryResponse(BaseModel):
    channel: ChannelType
    total: int
    incoming: int
    outgoing: int
    ai_resolved: int
    escalated: int


class TypesBreakdownResponse(BaseModel):
    channel: ChannelType
    incoming: int
    outgoing: int
    replied: int
    pending: int
    failed: int
    escalated: int


class RecentActivityItem(BaseModel):
    id: str
    channel: ChannelType
    direction: Optional[Literal["incoming", "outgoing"]] = None
    customer_contact: Optional[str] = None
    message_text: Optional[str] = None
    ai_response: Optional[str] = None
    created_at: str  # ISO


class RecentActivityResponse(BaseModel):
    items: List[RecentActivityItem]
    total: int


class AssistantPerformanceResponse(BaseModel):
    days: int
    total_interactions: int
    ai_resolved: int
    escalated: int
    ai_resolved_rate: float
    escalation_rate: float
    avg_confidence: Optional[float] = None

