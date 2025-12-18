from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from sqlalchemy.exc import SQLAlchemyError
from database import get_db
from models import Tenant, Channel, Message, VoiceMessage
from auth.dependencies import get_current_tenant
from schemas.analytics import (
    BasicAnalyticsResponse,
    MessageOverTimeItem,
    ChannelSummaryResponse,
    DailyCountItem,
    TypesBreakdownResponse,
    RecentActivityResponse,
    RecentActivityItem,
    AssistantPerformanceResponse,
)
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid

router = APIRouter()


def _tenant_channel_ids_by_type(db: Session, tenant_id, channel_type: str) -> List[uuid.UUID]:
    channels = db.query(Channel.id).filter(
        Channel.tenant_id == tenant_id,
        Channel.type == channel_type,
    ).all()
    return [row[0] for row in channels]


def _date_range(days: int) -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    start = now - timedelta(days=max(days, 1) - 1)
    return start, now


def _message_base_query(
    db: Session,
    tenant_id,
    channel_type: str,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
):
    channel_ids = _tenant_channel_ids_by_type(db, tenant_id, channel_type)
    query = db.query(Message).filter(
        Message.tenant_id == tenant_id,
        Message.channel_id.in_(channel_ids) if channel_ids else False,
    )
    if start_dt:
        query = query.filter(Message.created_at >= start_dt)
    if end_dt:
        query = query.filter(Message.created_at <= end_dt)
    return query


def _voice_base_query(
    db: Session,
    tenant_id,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
):
    # IMPORTANT (multitenancy + schema):
    # - Tenant ownership is determined via channels.tenant_id
    # - voice_messages table in the DB does NOT have voice_messages.tenant_id
    #   so we must avoid selecting the ORM entity (it would try to SELECT that column).
    query = db.query(
        VoiceMessage.id,
        VoiceMessage.channel_id,
        VoiceMessage.from_contact,
        VoiceMessage.transcription,
        VoiceMessage.ai_response,
        VoiceMessage.confidence_score,
        VoiceMessage.created_at,
        VoiceMessage.updated_at,
    ).join(
        Channel,
        VoiceMessage.channel_id == Channel.id,
    ).filter(
        Channel.tenant_id == tenant_id,
        Channel.type == "voice",
    )
    if start_dt:
        query = query.filter(VoiceMessage.created_at >= start_dt)
    if end_dt:
        query = query.filter(VoiceMessage.created_at <= end_dt)
    return query


@router.get("/basic", response_model=BasicAnalyticsResponse)
def get_basic_analytics(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Get basic analytics for the authenticated tenant.
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
        voice_count = db.query(func.count(VoiceMessage.id)).join(
            Channel,
            VoiceMessage.channel_id == Channel.id,
        ).filter(
            Channel.tenant_id == tenant_id,
            Channel.type == "voice",
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


# ======================================================
# Frontend-expected analytics endpoints
# ======================================================


@router.get("/{channel}/summary", response_model=ChannelSummaryResponse)
def get_channel_summary(
    channel: str,
    days: int = Query(30, ge=1, le=365),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Return simple counts for a single channel type."""
    if channel not in {"sms", "email", "chat", "voice"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel")

    try:
        tenant_id = current_tenant.id
        start_dt, end_dt = _date_range(days)

        if channel == "voice":
            q = _voice_base_query(db, tenant_id, start_dt, end_dt)
            total = q.count()
            avg_conf = db.query(func.avg(VoiceMessage.confidence_score)).join(
                Channel,
                VoiceMessage.channel_id == Channel.id,
            ).filter(
                Channel.tenant_id == tenant_id,
                Channel.type == "voice",
                VoiceMessage.created_at >= start_dt,
                VoiceMessage.created_at <= end_dt,
            ).scalar()

            return ChannelSummaryResponse(
                channel="voice",
                total=total,
                incoming=total,
                outgoing=0,
                ai_resolved=total,
                escalated=0,
            )

        q = _message_base_query(db, tenant_id, channel, start_dt, end_dt)
        total = q.count()

        incoming = q.filter(Message.direction == "incoming").count()
        outgoing = q.filter(Message.direction == "outgoing").count()

        ai_resolved = q.filter((Message.status == "replied") | (Message.escalated_to_human == False)).count()
        escalated = q.filter(Message.escalated_to_human == True).count()

        return ChannelSummaryResponse(
            channel=channel,  # type: ignore[arg-type]
            total=total,
            incoming=incoming,
            outgoing=outgoing,
            ai_resolved=ai_resolved,
            escalated=escalated,
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to retrieve summary",
        )


@router.get("/{channel}/daily", response_model=List[DailyCountItem])
def get_channel_daily(
    channel: str,
    days: int = Query(30, ge=1, le=365),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Return daily counts for the last N days for a channel."""
    if channel not in {"sms", "email", "chat", "voice"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel")

    try:
        tenant_id = current_tenant.id
        today = datetime.utcnow().date()
        start_date = today - timedelta(days=days - 1)

        if channel == "voice":
            rows = db.query(
                cast(VoiceMessage.created_at, Date).label("day"),
                func.count(VoiceMessage.id).label("count"),
            ).join(
                Channel,
                VoiceMessage.channel_id == Channel.id,
            ).filter(
                Channel.tenant_id == tenant_id,
                Channel.type == "voice",
                cast(VoiceMessage.created_at, Date) >= start_date,
                cast(VoiceMessage.created_at, Date) <= today,
            ).group_by(
                cast(VoiceMessage.created_at, Date)
            ).order_by(
                cast(VoiceMessage.created_at, Date)
            ).all()
        else:
            channel_ids = _tenant_channel_ids_by_type(db, tenant_id, channel)
            if not channel_ids:
                return [DailyCountItem(date=str(start_date + timedelta(days=i)), count=0) for i in range(days)]

            rows = db.query(
                cast(Message.created_at, Date).label("day"),
                func.count(Message.id).label("count"),
            ).filter(
                Message.tenant_id == tenant_id,
                Message.channel_id.in_(channel_ids),
                cast(Message.created_at, Date) >= start_date,
                cast(Message.created_at, Date) <= today,
            ).group_by(
                cast(Message.created_at, Date)
            ).order_by(
                cast(Message.created_at, Date)
            ).all()

        counts = {str(r.day): r.count for r in rows}
        return [
            DailyCountItem(date=str(start_date + timedelta(days=i)), count=counts.get(str(start_date + timedelta(days=i)), 0))
            for i in range(days)
        ]
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to retrieve daily analytics",
        )


@router.get("/{channel}/types", response_model=TypesBreakdownResponse)
def get_channel_types(
    channel: str,
    days: int = Query(30, ge=1, le=365),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Return a basic breakdown by direction/status for the last N days."""
    if channel not in {"sms", "email", "chat", "voice"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel")

    try:
        tenant_id = current_tenant.id
        start_dt, end_dt = _date_range(days)

        if channel == "voice":
            total = _voice_base_query(db, tenant_id, start_dt, end_dt).count()
            return TypesBreakdownResponse(
                channel="voice",
                incoming=total,
                outgoing=0,
                replied=total,
                pending=0,
                failed=0,
                escalated=0,
            )

        q = _message_base_query(db, tenant_id, channel, start_dt, end_dt)
        incoming = q.filter(Message.direction == "incoming").count()
        outgoing = q.filter(Message.direction == "outgoing").count()
        replied = q.filter(Message.status == "replied").count()
        pending = q.filter(Message.status == "pending").count()
        failed = q.filter(Message.status == "failed").count()
        escalated = q.filter(Message.escalated_to_human == True).count()

        return TypesBreakdownResponse(
            channel=channel,  # type: ignore[arg-type]
            incoming=incoming,
            outgoing=outgoing,
            replied=replied,
            pending=pending,
            failed=failed,
            escalated=escalated,
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to retrieve type breakdown",
        )


@router.get("/recent-activity", response_model=RecentActivityResponse)
def get_recent_activity(
    limit: int = Query(20, ge=1, le=200),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Return recent activity across sms/email/chat/voice, newest first."""
    try:
        tenant_id = current_tenant.id

        # Latest message rows (sms/email/chat)
        channel_rows = db.query(Channel.id, Channel.type).filter(Channel.tenant_id == tenant_id).all()
        channel_type_by_id = {row[0]: row[1] for row in channel_rows}

        message_rows = db.query(Message).filter(
            Message.tenant_id == tenant_id
        ).order_by(Message.created_at.desc()).limit(limit).all()

        voice_rows = db.query(
            VoiceMessage.id,
            VoiceMessage.from_contact,
            VoiceMessage.transcription,
            VoiceMessage.ai_response,
            VoiceMessage.created_at,
        ).join(
            Channel,
            VoiceMessage.channel_id == Channel.id,
        ).filter(
            Channel.tenant_id == tenant_id,
            Channel.type == "voice",
        ).order_by(VoiceMessage.created_at.desc()).limit(limit).all()

        items: List[RecentActivityItem] = []
        for msg in message_rows:
            ch_type = channel_type_by_id.get(msg.channel_id)
            if ch_type not in {"sms", "email", "chat"}:
                continue
            items.append(
                RecentActivityItem(
                    id=str(msg.id),
                    channel=ch_type,  # type: ignore[arg-type]
                    direction=msg.direction if msg.direction in {"incoming", "outgoing"} else None,
                    customer_contact=msg.customer_contact,
                    message_text=msg.message_text,
                    ai_response=msg.ai_response,
                    created_at=msg.created_at.isoformat(),
                )
            )

        for v in voice_rows:
            items.append(
                RecentActivityItem(
                    id=str(v[0]),
                    channel="voice",
                    direction="incoming",
                    customer_contact=v[1],
                    message_text=v[2],
                    ai_response=v[3],
                    created_at=v[4].isoformat(),
                )
            )

        items.sort(key=lambda x: x.created_at, reverse=True)
        items = items[:limit]

        return RecentActivityResponse(items=items, total=len(items))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to retrieve recent activity",
        )


@router.get("/assistant-performance", response_model=AssistantPerformanceResponse)
def get_assistant_performance(
    days: int = Query(30, ge=1, le=365),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Basic AI performance metrics across all channels."""
    try:
        tenant_id = current_tenant.id
        start_dt, end_dt = _date_range(days)

        msg_q = db.query(Message).filter(
            Message.tenant_id == tenant_id,
            Message.created_at >= start_dt,
            Message.created_at <= end_dt,
        )
        # Voice interactions: count only (avoid selecting VoiceMessage ORM entity)
        total_voice = db.query(func.count(VoiceMessage.id)).join(
            Channel,
            VoiceMessage.channel_id == Channel.id,
        ).filter(
            Channel.tenant_id == tenant_id,
            Channel.type == "voice",
            VoiceMessage.created_at >= start_dt,
            VoiceMessage.created_at <= end_dt,
        ).scalar() or 0

        total_msgs = msg_q.count()
        total_interactions = total_msgs + total_voice

        ai_resolved_msgs = msg_q.filter((Message.status == "replied") | (Message.escalated_to_human == False)).count()
        escalated_msgs = msg_q.filter(Message.escalated_to_human == True).count()

        avg_msg_conf = db.query(func.avg(Message.confidence_score)).filter(
            Message.tenant_id == tenant_id,
            Message.created_at >= start_dt,
            Message.created_at <= end_dt,
        ).scalar()
        avg_voice_conf = db.query(func.avg(VoiceMessage.confidence_score)).filter(
            Channel.tenant_id == tenant_id,
            Channel.type == "voice",
            VoiceMessage.channel_id == Channel.id,
            VoiceMessage.created_at >= start_dt,
            VoiceMessage.created_at <= end_dt,
        ).scalar()

        conf_values = [v for v in [avg_msg_conf, avg_voice_conf] if v is not None]
        avg_confidence = float(sum(conf_values) / len(conf_values)) if conf_values else None

        ai_resolved = ai_resolved_msgs + total_voice
        escalated = escalated_msgs

        ai_resolved_rate = (ai_resolved / total_interactions) if total_interactions else 0.0
        escalation_rate = (escalated / total_interactions) if total_interactions else 0.0

        return AssistantPerformanceResponse(
            days=days,
            total_interactions=total_interactions,
            ai_resolved=ai_resolved,
            escalated=escalated,
            ai_resolved_rate=float(ai_resolved_rate),
            escalation_rate=float(escalation_rate),
            avg_confidence=avg_confidence,
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to retrieve assistant performance",
        )

