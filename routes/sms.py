from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Tenant, Channel, Message
from ai_providers import get_ai_response
from datetime import datetime
import uuid
from fastapi.responses import Response

router = APIRouter()

@router.post("/receive")  # full path will be /sms/receive
async def receive_sms(request: Request):
    data = await request.form()
    from_number = data.get("From")   # sender number (renamed for consistency)
    message_text = data.get("Body")  # message body
    to_number = data.get("To")       # Twilio number received

    # check required fields
    if not from_number or not message_text or not to_number:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields. Got From={from_number}, Body={message_text}, To={to_number}"
        )

    db: Session = SessionLocal()

    # Find the channel by the Twilio number (multi-tenant)
    channel = db.query(Channel).filter(Channel.type=="sms", Channel.identifier==to_number).first()
    if not channel:
        raise HTTPException(status_code=404, detail=f"SMS channel for {to_number} not found")

    # Get tenant via channel
    tenant = db.query(Tenant).filter(Tenant.id == channel.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Get AI response for this tenant
    ai_reply, confidence = get_ai_response(
        message_text=message_text,
        ai_provider=tenant.ai_provider,
        system_prompt=tenant.ai_system_prompt,
        model=getattr(tenant, "ai_model", None),
        temperature=getattr(tenant, "ai_temperature", None)
    )

    # Save message
    message = Message(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        channel_id=channel.id,
        message_text=message_text,
        ai_response=ai_reply,
        confidence_score=confidence,
        status="replied",
        escalated_to_human=False,
        direction="incoming",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        customer_contact=from_number, 
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    # Twilio XML response
    twilio_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{ai_reply}</Message>
</Response>"""
    return Response(content=twilio_response, media_type="application/xml")
