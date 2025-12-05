from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_
from database import SessionLocal, get_db
from models import Tenant, Channel, Message, Appointment
from ai_providers import get_ai_response, parse_appointment_from_user_message
from auth.dependencies import get_current_tenant
from schemas.sms import SMSMessageResponse, SMSMessageListResponse, SendSMSRequest, SendSMSResponse
from datetime import datetime, timedelta
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from config import settings
import uuid
from fastapi.responses import Response
from typing import List

router = APIRouter()

# Initialize Twilio client
twilio_client = None
if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
    twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def check_slot_available(db: Session, tenant_id, requested_time: datetime, duration_minutes: int = 60) -> bool:
    """Check if the requested time slot is available."""
    slot_end = requested_time + timedelta(minutes=duration_minutes)
    existing = db.query(Appointment).filter(
        and_(
            Appointment.tenant_id == tenant_id,
            Appointment.status.in_(["confirmed", "pending"]),
            Appointment.confirmed_time < slot_end,
            Appointment.confirmed_time >= requested_time - timedelta(minutes=duration_minutes)
        )
    ).first()
    return existing is None


def get_available_slots(db: Session, tenant_id, requested_date: datetime, open_hour: int, close_hour: int) -> list:
    """Get available time slots for a given date."""
    day_start = requested_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    booked_times = db.query(Appointment.confirmed_time).filter(
        and_(
            Appointment.tenant_id == tenant_id,
            Appointment.status.in_(["confirmed", "pending"]),
            Appointment.confirmed_time >= day_start,
            Appointment.confirmed_time < day_end
        )
    ).all()

    booked_hours = {bt[0].hour for bt in booked_times if bt[0]}
    available_slots = []

    for hour in range(open_hour, close_hour):
        if hour not in booked_hours:
            slot_time = requested_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            if slot_time > datetime.utcnow():
                available_slots.append(slot_time)

    return available_slots[:3]


@router.post("/receive")
async def receive_sms(request: Request):
    data = await request.form()
    from_number = data.get("From")
    message_text = data.get("Body")
    to_number = data.get("To")

    if not from_number or not message_text or not to_number:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields. Got From={from_number}, Body={message_text}, To={to_number}"
        )

    db: Session = SessionLocal()
    try:
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

        # Get working hours
        open_hour = int(tenant.open_time.split(":")[0]) if tenant.open_time else 9
        close_hour = int(tenant.close_time.split(":")[0]) if tenant.close_time else 17

        # --- Extract Appointment from USER TEXT FIRST ---
        tenant_settings = {"services": tenant.services or []}
        try:
            appointment_info = parse_appointment_from_user_message(message_text, tenant_settings=tenant_settings)
        except Exception:
            appointment_info = None

        # If appointment info detected with both time and service
        if appointment_info:
            appointment_time = appointment_info.get("datetime")
            service_name = appointment_info.get("service")

            if appointment_time and service_name:
                # Check if within working hours
                if open_hour <= appointment_time.hour < close_hour:
                    # Check availability
                    if check_slot_available(db, tenant.id, appointment_time):
                        # SLOT AVAILABLE - Create appointment directly
                        appointment = Appointment(
                            id=uuid.uuid4(),
                            tenant_id=tenant.id,
                            channel_id=channel.id,
                            customer_contact=from_number,
                            requested_time=appointment_time,
                            confirmed_time=appointment_time,
                            service=service_name,
                            status="confirmed",
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        )
                        db.add(appointment)

                        confirmation_text = (
                            f"Great! Your appointment for {service_name} is confirmed on "
                            f"{appointment_time.strftime('%A, %B %d, %Y at %I:%M %p')}. "
                            f"We look forward to seeing you!"
                        )

                        message = Message(
                            id=uuid.uuid4(),
                            tenant_id=tenant.id,
                            channel_id=channel.id,
                            message_text=message_text,
                            ai_response=confirmation_text,
                            confidence_score=1.0,
                            status="replied",
                            escalated_to_human=False,
                            direction="incoming",
                            customer_contact=from_number,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        )
                        db.add(message)
                        db.commit()

                        return Response(
                            content=f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{confirmation_text}</Message></Response>',
                            media_type="application/xml"
                        )

                    else:
                        # SLOT NOT AVAILABLE - Get suggestions
                        available_slots = get_available_slots(db, tenant.id, appointment_time, open_hour, close_hour)

                        if available_slots:
                            slots_text = ", ".join([s.strftime("%I:%M %p") for s in available_slots])
                            suggestion_text = (
                                f"Sorry, {appointment_time.strftime('%I:%M %p')} on "
                                f"{appointment_time.strftime('%B %d')} is not available for {service_name}. "
                                f"Available times: {slots_text}. Please reply with your preferred time."
                            )
                        else:
                            suggestion_text = (
                                f"Sorry, no availability on {appointment_time.strftime('%B %d')} for {service_name}. "
                                f"Please try another date."
                            )

                        message = Message(
                            id=uuid.uuid4(),
                            tenant_id=tenant.id,
                            channel_id=channel.id,
                            message_text=message_text,
                            ai_response=suggestion_text,
                            confidence_score=0.9,
                            status="replied",
                            escalated_to_human=False,
                            direction="incoming",
                            customer_contact=from_number,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow()
                        )
                        db.add(message)
                        db.commit()

                        return Response(
                            content=f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{suggestion_text}</Message></Response>',
                            media_type="application/xml"
                        )

                else:
                    # Outside working hours
                    outside_text = (
                        f"Sorry, we're open {open_hour}:00 AM to {close_hour}:00 PM. "
                        f"Please choose a time within our hours for {service_name}."
                    )

                    message = Message(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        channel_id=channel.id,
                        message_text=message_text,
                        ai_response=outside_text,
                        confidence_score=0.9,
                        status="replied",
                        escalated_to_human=False,
                        direction="incoming",
                        customer_contact=from_number,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(message)
                    db.commit()

                    return Response(
                        content=f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{outside_text}</Message></Response>',
                        media_type="application/xml"
                    )

        # --- NO appointment detected → Regular AI response ---
        ai_reply, confidence = get_ai_response(
            message_text=message_text,
            ai_provider=tenant.ai_provider or "openai",
            system_prompt=tenant.ai_system_prompt or ""
        )

        message = Message(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            channel_id=channel.id,
            message_text=message_text,
            ai_response=ai_reply,
            confidence_score=confidence,
            status="replied",
            escalated_to_human=False,
            direction="incoming",
            customer_contact=from_number,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(message)
        db.commit()

        return Response(
            content=f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{ai_reply}</Message></Response>',
            media_type="application/xml"
        )

    finally:
        db.close()

# ==========================================
# 📌 GET /messages/sms - Get all SMS messages for tenant
# ==========================================
@router.get("/messages", response_model=SMSMessageListResponse)
def get_sms_messages(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Get all SMS messages for the authenticated tenant.
    Returns messages ordered by created_at ascending.
    """
    # Get all SMS channels for this tenant
    sms_channels = db.query(Channel).filter(
        Channel.tenant_id == current_tenant.id,
        Channel.type == "sms"
    ).all()

    if not sms_channels:
        return SMSMessageListResponse(messages=[], total=0)

    channel_ids = [ch.id for ch in sms_channels]

    # Query messages for SMS channels
    messages = db.query(Message).filter(
        Message.tenant_id == current_tenant.id,
        Message.channel_id.in_(channel_ids)
    ).order_by(Message.created_at.asc()).all()

    # Convert to response format
    message_list = [
        SMSMessageResponse(
            id=str(msg.id),
            customer_contact=msg.customer_contact or "",
            message_text=msg.message_text,
            direction=msg.direction or "incoming",
            created_at=msg.created_at,
            ai_response=msg.ai_response
        )
        for msg in messages
    ]

    return SMSMessageListResponse(messages=message_list, total=len(message_list))


# ==========================================
# 📌 POST /messages/sms/send - Send SMS via Twilio
# ==========================================
@router.post("/messages/send", response_model=SendSMSResponse)
def send_sms(
    request: SendSMSRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Send an SMS message via Twilio.
    Validates tenant ownership of channel and stores outgoing message.
    """
    # Check Twilio client is configured
    if not twilio_client:
        raise HTTPException(
            status_code=500,
            detail="Twilio is not configured. Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
        )

    # Validate channel belongs to tenant
    channel = db.query(Channel).filter(
        Channel.id == request.channel_id,
        Channel.tenant_id == current_tenant.id,
        Channel.type == "sms"
    ).first()

    if not channel:
        raise HTTPException(
            status_code=404,
            detail="SMS channel not found or does not belong to this tenant"
        )

    # Send SMS via Twilio
    try:
        twilio_message = twilio_client.messages.create(
            body=request.message_text,
            from_=channel.identifier,
            to=request.to
        )
    except TwilioRestException as e:
        raise HTTPException(
            status_code=400,
            detail=f"Twilio error: {e.msg}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send SMS: {str(e)}"
        )

    # Store outgoing message in database
    message = Message(
        id=uuid.uuid4(),
        tenant_id=current_tenant.id,
        channel_id=channel.id,
        direction="outgoing",
        message_text=request.message_text,
        ai_response=None,
        confidence_score=None,
        status="sent",
        escalated_to_human=False,
        customer_contact=request.to,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return SendSMSResponse(
        success=True,
        message_id=str(message.id),
        status="sent",
        to=request.to,
        message_text=request.message_text,
        twilio_sid=twilio_message.sid
    )
