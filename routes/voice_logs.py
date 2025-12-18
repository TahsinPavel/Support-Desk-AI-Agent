from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database import get_db
from models import Tenant, VoiceMessage, Channel
from auth.dependencies import get_current_tenant
from schemas.voice import VoiceLogResponse, VoiceLogListResponse
from typing import List

router = APIRouter()


@router.get("/logs", response_model=VoiceLogListResponse)
def get_voice_logs(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Get all voice call logs for the authenticated tenant.
    Returns logs ordered by created_at descending (most recent first).
    
    Requires: Bearer token authentication
    
    Returns:
        - 200: List of voice logs
        - 401: Unauthorized (no/invalid token)
        - 404: No voice logs found
        - 500: Database query failed
    """
    try:
        # IMPORTANT (multitenancy + schema):
        # - Tenant ownership is determined via channels.tenant_id
        # - voice_messages table in the DB does NOT have voice_messages.tenant_id
        #   so we must avoid selecting the ORM entity (it would try to SELECT that column).
        voice_messages = db.query(
            VoiceMessage.id,
            VoiceMessage.from_contact,
            VoiceMessage.transcription,
            VoiceMessage.ai_response,
            VoiceMessage.confidence_score,
            VoiceMessage.created_at,
        ).join(
            Channel,
            VoiceMessage.channel_id == Channel.id,
        ).filter(
            Channel.tenant_id == current_tenant.id,
            Channel.type == "voice",
        ).order_by(VoiceMessage.created_at.desc()).all()

        # Check if any logs exist
        if not voice_messages:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No voice logs found for this tenant"
            )

        # Convert to response format
        logs = [
            VoiceLogResponse(
                id=row[0],
                from_contact=row[1],
                transcription=row[2],
                ai_response=row[3],
                confidence_score=row[4],
                created_at=row[5],
            )
            for row in voice_messages
        ]

        return VoiceLogListResponse(logs=logs, total=len(logs))

    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: Failed to retrieve voice logs"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

