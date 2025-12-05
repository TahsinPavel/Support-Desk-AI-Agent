from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class VoiceLogResponse(BaseModel):
    """Single voice log entry response."""
    id: UUID
    from_contact: Optional[str] = None
    transcription: Optional[str] = None
    ai_response: Optional[str] = None
    confidence_score: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class VoiceLogListResponse(BaseModel):
    """List of voice logs."""
    logs: List[VoiceLogResponse]
    total: int

