from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Tenant, Channel, Message, Appointment
from ai_providers import get_ai_response, parse_appointment_from_user_message
from datetime import datetime
import uuid
from fastapi.responses import Response

router = APIRouter()

@router.post("/receive")
async def receive_sms(request: Request):
    data = await request.form()
    from_number = data.get("From")
    message_text = data.get("Body")
    to_number = data.get("To")

    # Validate
    if not from_number or not message_text or not to_number:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields. Got From={from_number}, Body={message_text}, To={to_number}"
        )

    db: Session = SessionLocal()

    # Get channel
    channel = db.query(Channel).filter(
        Channel.type == "sms",
        Channel.identifier == to_number
    ).first()

    if not channel:
        raise HTTPException(status_code=404, detail=f"SMS channel for {to_number} not found")

    # Get tenant
    tenant = db.query(Tenant).filter(Tenant.id == channel.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Fetch previous messages
    previous_messages = db.query(Message).filter(
        Message.customer_contact == from_number,
        Message.tenant_id == tenant.id
    ).order_by(Message.created_at.desc()).all()

    # --- AI RESPONSE ---
    ai_reply, confidence = get_ai_response(
        message_text=message_text,
        ai_provider=tenant.ai_provider,
        system_prompt=tenant.ai_system_prompt,
        model=getattr(tenant, "ai_model", None),
        temperature=getattr(tenant, "ai_temperature", None)
    )

    # Save message in DB
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

    # --- Extract Appointment from USER TEXT ---
    # (NOT from AI reply)
    tenant_settings = {"services": tenant.services or []}

    try:
        appointment_info = parse_appointment_from_user_message(
            message_text,
            tenant_settings=tenant_settings
        )
    except Exception:
        appointment_info = None

    # Send AI reply first ALWAYS
    twilio_base_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{ai_reply}</Message>
</Response>"""

    # If NO appointment detected → return only AI reply
    if not appointment_info:
        return Response(content=twilio_base_response, media_type="application/xml")

    # Extract fields
    appointment_time = appointment_info.get("datetime")
    service_name = appointment_info.get("service")

    # Validation
    if not appointment_time or not service_name:
        # Still return the AI’s original reply only
        return Response(content=twilio_base_response, media_type="application/xml")

    # Check working hours
    open_hour = int(tenant.open_time.split(":")[0]) if tenant.open_time else 9
    close_hour = int(tenant.close_time.split(":")[0]) if tenant.close_time else 17

    if not (open_hour <= appointment_time.hour < close_hour):
        # Still only respond with the AI reply
        return Response(content=twilio_base_response, media_type="application/xml")

    # --- Create Appointment ---
    appointment = Appointment(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        channel_id=channel.id,
        customer_contact=from_number,
        appointment_time=appointment_time,
        service=service_name,
        status="confirmed",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    # Send confirmation message separately
    confirmation_text = (
        f"Your appointment for {service_name} is booked on "
        f"{appointment_time.strftime('%A, %d %B %Y at %I:%M %p')}."
    )

    twilio_confirmation_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{confirmation_text}</Message>
</Response>"""

    return Response(content=twilio_confirmation_response, media_type="application/xml")
