from fastapi import APIRouter, Request, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database import SessionLocal, get_db
from models import Tenant, Channel, Message
from auth.dependencies import get_current_tenant
from schemas.email import (
    EmailMessageResponse,
    EmailMessageListResponse,
    SendEmailRequest,
    SendEmailResponse,
    ReceiveEmailRequest
)
from ai_providers import get_ai_response
import uuid
from datetime import datetime
from typing import Optional

router = APIRouter()


# ==========================================
# Utility: Get or Create Email Channel
# ==========================================
def get_or_create_email_channel(db: Session, tenant: Tenant) -> Channel:
    """
    Get existing email channel for tenant, or create one if it doesn't exist.
    Uses a default email pattern based on business name.
    """
    channel = db.query(Channel).filter(
        Channel.tenant_id == tenant.id,
        Channel.type == "email"
    ).first()

    if not channel:
        # Auto-create email channel
        email_identifier = f"support@{tenant.business_name.lower().replace(' ', '')}.com"
        channel = Channel(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            type="email",
            identifier=email_identifier,
            description="Auto-created email channel",
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)

    return channel


# ==========================================
# 1️⃣ GET /email/messages - Get all emails for tenant
# ==========================================
@router.get("/messages", response_model=EmailMessageListResponse)
def get_email_messages(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Get all email messages for the authenticated tenant.
    Returns emails ordered by created_at descending (most recent first).
    """
    try:
        # Get email channels for this tenant
        email_channels = db.query(Channel).filter(
            Channel.tenant_id == current_tenant.id,
            Channel.type == "email"
        ).all()

        if not email_channels:
            return EmailMessageListResponse(emails=[], total=0)

        channel_ids = [ch.id for ch in email_channels]
        # Map channel identifiers for from/to email resolution
        channel_map = {ch.id: ch.identifier for ch in email_channels}

        # Query messages for email channels
        messages = db.query(Message).filter(
            Message.tenant_id == current_tenant.id,
            Message.channel_id.in_(channel_ids)
        ).order_by(Message.created_at.desc()).all()

        # Convert to response format
        email_list = []
        for msg in messages:
            channel_email = channel_map.get(msg.channel_id, "")

            # Determine from/to based on direction
            if msg.direction == "incoming":
                from_email = msg.customer_contact
                to_email = channel_email
            else:
                from_email = channel_email
                to_email = msg.customer_contact

            email_list.append(
                EmailMessageResponse(
                    id=str(msg.id),
                    subject=None,  # Subject stored in message_text prefix if needed
                    from_email=from_email,
                    to_email=to_email,
                    message_text=msg.message_text,
                    direction=msg.direction or "incoming",
                    ai_response=msg.ai_response,
                    created_at=msg.created_at
                )
            )

        return EmailMessageListResponse(emails=email_list, total=len(email_list))

    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to retrieve emails"
        )


# ==========================================
# 2️⃣ POST /email/send - Send outgoing email
# ==========================================
@router.post("/send", response_model=SendEmailResponse)
def send_email(
    request: SendEmailRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Send an outgoing email and store it in the database.
    Auto-creates email channel if tenant doesn't have one.
    """
    try:
        # Get or create email channel for tenant
        channel = get_or_create_email_channel(db, current_tenant)

        # Store outgoing email in database
        message = Message(
            id=uuid.uuid4(),
            tenant_id=current_tenant.id,
            channel_id=channel.id,
            direction="outgoing",
            message_text=f"[Subject: {request.subject}]\n\n{request.message}",
            ai_response=None,
            confidence_score=None,
            status="sent",
            escalated_to_human=False,
            customer_contact=request.to_email,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        # TODO: Integrate with actual SMTP provider (SendGrid, SES, etc.)
        # For now, we just store the message without sending
        # Example:
        # smtp_service.send(
        #     from_email=channel.identifier,
        #     to_email=request.to_email,
        #     subject=request.subject,
        #     body=request.message
        # )

        return SendEmailResponse(
            status="sent",
            message_id=str(message.id)
        )

    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to send email"
        )


# ==========================================
# 3️⃣ POST /email/receive - Webhook for incoming emails
# ==========================================
@router.post("/receive")
async def receive_email(request: Request):
    """
    Webhook endpoint for receiving incoming emails.
    Processes with AI and stores in database.
    """
    data = await request.json()
    customer_email = data.get("customer_email")
    subject = data.get("subject", "")
    message_text = data.get("message")
    tenant_id = data.get("tenant_id")

    if not customer_email or not message_text or not tenant_id:
        raise HTTPException(status_code=400, detail="Missing required fields")

    db: Session = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Get or create email channel
        channel = get_or_create_email_channel(db, tenant)

        # Get AI response
        ai_reply, confidence = get_ai_response(
            message_text=message_text,
            ai_provider=tenant.ai_provider or "openai",
            system_prompt=tenant.ai_system_prompt or "",
            model=getattr(tenant, "ai_model", None),
            temperature=getattr(tenant, "ai_temperature", 0.7)
        )

        # Store incoming email
        full_message = f"[Subject: {subject}]\n\n{message_text}" if subject else message_text
        message = Message(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            channel_id=channel.id,
            customer_contact=customer_email,
            message_text=full_message,
            ai_response=ai_reply,
            confidence_score=confidence,
            status="replied",
            escalated_to_human=False,
            direction="incoming",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(message)
        db.commit()

        return {
            "customer_message": message_text,
            "subject": subject,
            "ai_reply": ai_reply,
            "confidence": confidence,
            "provider_used": tenant.ai_provider
        }
    finally:
        db.close()