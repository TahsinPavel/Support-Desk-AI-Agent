from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User, Channel, Message
from ai_providers import get_ai_response
from datetime import datetime
import uuid

router = APIRouter()

@router.post("/chat/receive")
async def receive_chat(request: Request):
    data = await request.json()
    customer_name = data.get("customer_name")
    message_text = data.get("message")
    user_id = data.get("user_id")  # tenant

    if not customer_name or not message_text or not user_id:
        raise HTTPException(status_code=400, detail="Missing required fields")

    db: Session = SessionLocal()
    tenant = db.query(User).filter(User.id == user_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    channel = db.query(Channel).filter(Channel.user_id == user_id, Channel.type == "chat").first()
    if not channel:
        raise HTTPException(status_code=404, detail="Chat channel not found")

    ai_reply, confidence = get_ai_response(
        message_text=message_text,
        ai_provider=tenant.ai_provider,
        system_prompt=tenant.ai_system_prompt,
        model=tenant.ai_model,
        temperature=tenant.ai_temperature
    )

    message = Message(
        id=uuid.uuid4(),
        channel_id=channel.id,
        customer_contact=None,
        customer_name=customer_name,
        message_text=message_text,
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

    return {"customer_message": message_text, "ai_reply": ai_reply, "confidence": confidence, "provider_used": tenant.ai_provider}
