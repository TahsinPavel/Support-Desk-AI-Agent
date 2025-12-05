from pydantic import BaseModel
from typing import List
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

