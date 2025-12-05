from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Tenant, Channel, VoiceMessage
from ai_providers import get_ai_response
from datetime import datetime
import uuid

router = APIRouter()

@router.post("/receive")
async def voice_webhook(request: Request):
    data = await request.form()
    from_number = data.get("From")
    to_number = data.get("To")
    call_sid = data.get("CallSid")
    speech_text = data.get("SpeechResult")  # from Twilio only exists after <Gather>
    transcription_to_store = speech_text if speech_text else None

    if not from_number or not to_number or not call_sid:
        raise HTTPException(status_code=400, detail="Missing required fields")

    db: Session = SessionLocal()

    # Find voice channel
    channel = db.query(Channel).filter(Channel.type=="voice", Channel.identifier==to_number).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Voice channel not found")

    # Find tenant by Twilio number
    tenant = db.query(Tenant).filter(Tenant.id == channel.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # First call, no SpeechResult yet → greet
    if not speech_text:
        twilio_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Hello! This is {tenant.business_name}. How can I help you today?</Say>
    <Gather input="speech" action="/voice/receive" method="POST" speechTimeout="auto"/>
</Response>"""
        return Response(content=twilio_response, media_type="application/xml")

    # Process user speech with AI
    ai_reply, confidence = get_ai_response(
        message_text=speech_text,
        ai_provider=tenant.ai_provider,
        system_prompt=tenant.ai_system_prompt,
        model=getattr(tenant, "ai_model", None),
        temperature=getattr(tenant, "ai_temperature", None)
    )

    # Save conversation in voice_messages
    message = VoiceMessage(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        channel_id=channel.id,
        from_contact=from_number,
        transcription=transcription_to_store,
        ai_response=ai_reply,
        confidence_score=confidence,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(message)
    db.commit()

    # Respond to user with AI reply, continue gathering
    twilio_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{ai_reply}</Say>
    <Gather input="speech" action="/voice/receive" method="POST" speechTimeout="auto"/>
</Response>"""

    return Response(content=twilio_response, media_type="application/xml")