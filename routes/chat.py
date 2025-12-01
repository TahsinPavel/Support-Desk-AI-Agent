from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from models import Tenant, Channel, Message
from ai_providers import get_ai_response
from datetime import datetime
from uuid import UUID
from database import get_db

router = APIRouter()

@router.post("/receive")
async def receive_chat(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    channel_id = data.get("channel_id")
    message_text = data.get("message_text")

    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id is required")
    if not message_text:
        raise HTTPException(status_code=400, detail="message_text is required")

    try:
        channel_uuid = UUID(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel_id UUID format")

    channel = db.query(Channel).filter(Channel.id == channel_uuid).first()
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    # Get the tenant for AI settings
    tenant = db.query(Tenant).filter(Tenant.id == channel.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Get AI response
    ai_reply, confidence = get_ai_response(
        message_text=message_text,
        ai_provider=tenant.ai_provider or "openai",
        system_prompt=tenant.ai_system_prompt or ""
    )

    # Determine status based on confidence
    status = "replied" if confidence > 0.7 else "escalated"

    message = Message(
        tenant_id=tenant.id,
        channel_id=channel.id,
        direction=data.get("direction", "incoming"),
        message_text=message_text,
        ai_response=ai_reply,
        confidence_score=confidence,
        status=status,
        escalated_to_human=confidence <= 0.7,
        customer_contact=data.get("customer_contact", "anonymous")
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return {
        "id": str(message.id),
        "tenant_id": str(message.tenant_id),
        "channel_id": str(message.channel_id),
        "message_text": message.message_text,
        "ai_reply": ai_reply,
        "confidence": confidence,
        "status": message.status,
        "provider_used": tenant.ai_provider,
        "created_at": message.created_at.isoformat(),
    }