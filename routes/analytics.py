from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from sqlalchemy.exc import SQLAlchemyError
from database import get_db
from models import Tenant, Channel, Message, VoiceMessage
from auth.dependencies import get_current_tenant
from schemas.analytics import BasicAnalyticsResponse, MessageOverTimeItem
from datetime import datetime, timedelta
from typing import Dict

router = APIRouter()


@router.get("/basic", response_model=BasicAnalyticsResponse)
def get_basic_analytics(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Get basic analytics for the authenticated tenant.
    Returns aggregated statistics for messages, voice calls, and channels.
    """
    try:
        tenant_id = current_tenant.id
        # 1. Total Messages (all channels)
        total_messages = db.query(func.count(Message.id)).filter(
            Message.tenant_id == tenant_id
        ).scalar() or 0

        # 2. AI Resolved: status='replied' OR escalated_to_human=False
        ai_resolved = db.query(func.count(Message.id)).filter(
            Message.tenant_id == tenant_id,
            (Message.status == 'replied') | (Message.escalated_to_human == False)
        ).scalar() or 0

        # 3. Escalated count
        escalated = db.query(func.count(Message.id)).filter(
            Message.tenant_id == tenant_id,
            Message.escalated_to_human == True
        ).scalar() or 0

        # 4.Get all channels for this tenant
        channels = db.query(Channel).filter(
            Channel.tenant_id == tenant_id
        ).all()

        # Create channel type mapping
        channel_type_map: Dict[str, list] = {
            "sms": [],
            "email": [],
            "chat": []
        }
        for ch in channels:
            if ch.type in channel_type_map:
                channel_type_map[ch.type].append(ch.id)

        # Count messages by channel type
        sms_count = 0
        email_count = 0
        chat_count = 0

        if channel_type_map["sms"]:
            sms_count = db.query(func.count(Message.id)).filter(
                Message.tenant_id == tenant_id,
                Message.channel_id.in_(channel_type_map["sms"])
            ).scalar() or 0

        if channel_type_map["email"]:
            email_count = db.query(func.count(Message.id)).filter(
                Message.tenant_id == tenant_id,
                Message.channel_id.in_(channel_type_map["email"])
            ).scalar() or 0

        if channel_type_map["chat"]:
            chat_count = db.query(func.count(Message.id)).filter(
                Message.tenant_id == tenant_id,
                Message.channel_id.in_(channel_type_map["chat"])
            ).scalar() or 0

        # 5. Voice count from voice_messages table
        voice_count = db.query(func.count(VoiceMessage.id)).filter(
            VoiceMessage.tenant_id == tenant_id
        ).scalar() or 0

        # 6. Messages over time (last 14 days)
        today = datetime.utcnow().date()
        fourteen_days_ago = today - timedelta(days=13)

        # Query messages grouped by day
        daily_counts = db.query(
            cast(Message.created_at, Date).label('day'),
            func.count(Message.id).label('count')
        ).filter(
            Message.tenant_id == tenant_id,
            cast(Message.created_at, Date) >= fourteen_days_ago,
            cast(Message.created_at, Date) <= today
        ).group_by(
            cast(Message.created_at, Date)
        ).order_by(
            cast(Message.created_at, Date)
        ).all()

        # Create a dict for quick lookup
        counts_dict = {str(row.day): row.count for row in daily_counts}

        # Build full 14-day list with 0 for missing days
        messages_over_time = []
        for i in range(14):
            day = fourteen_days_ago + timedelta(days=i)
            day_str = str(day)
            messages_over_time.append(
                MessageOverTimeItem(
                    date=day_str,
                    count=counts_dict.get(day_str, 0)
                )
            )

        return BasicAnalyticsResponse(
            total_messages=total_messages,
            ai_resolved=ai_resolved,
            escalated=escalated,
            sms_count=sms_count,
            email_count=email_count,
            chat_count=chat_count,
            voice_count=voice_count,
            messages_over_time=messages_over_time
        )

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to retrieve analytics"
        )

