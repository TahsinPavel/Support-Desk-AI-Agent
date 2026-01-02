import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_current_tenant
from database import get_db
from models import Channel, Message, Tenant
from schemas.whatsapp import (
    MetaWhatsAppConnectRequest,
    MetaWhatsAppConnectResponse,
    WhatsAppConnectRequest,
    WhatsAppConnectResponse,
)

from ai_providers import get_ai_response
from config import settings
from services.meta_whatsapp import send_whatsapp_text_message, verify_meta_signature

router = APIRouter()


_E164_RE = re.compile(r"^\+?[1-9]\d{6,14}$")


def _normalize_whatsapp_identifier(value: str) -> str:
    raw = (value or "").strip()
    if raw.lower().startswith("whatsapp:"):
        raw = raw.split(":", 1)[1].strip()

    if not _E164_RE.match(raw):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid WhatsApp number. Use E.164 format like +14155550123",
        )

    if not raw.startswith("+"):
        raw = "+" + raw

    # Store using Twilio-style identifier format
    return f"whatsapp:{raw}"


@router.post("/connect", response_model=WhatsAppConnectResponse)
def connect_whatsapp(
    payload: WhatsAppConnectRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Connect a tenant's business WhatsApp number.

    This endpoint stores the number so the system can send/route WhatsApp messages for the tenant.
    Provider-side verification (Meta/Twilio) is a separate step.
    """

    identifier = _normalize_whatsapp_identifier(payload.whatsapp_number)

    existing = (
        db.query(Channel)
        .filter(
            Channel.tenant_id == current_tenant.id,
            Channel.type == "whatsapp",
            Channel.identifier == identifier,
        )
        .first()
    )

    if existing:
        return WhatsAppConnectResponse(
            success=True,
            message="WhatsApp number already connected",
            channel_id=existing.id,
            identifier=existing.identifier,
        )

    channel = Channel(
        tenant_id=current_tenant.id,
        type="whatsapp",
        identifier=identifier,
        status="pending",
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    return WhatsAppConnectResponse(
        success=True,
        message="WhatsApp number saved. Complete Meta Cloud API connection to enable automation.",
        channel_id=channel.id,
        identifier=channel.identifier,
    )


@router.post("/meta/connect", response_model=MetaWhatsAppConnectResponse)
def connect_meta_whatsapp(
    payload: MetaWhatsAppConnectRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Connect a tenant to Meta WhatsApp Cloud API.

    The key piece we need to receive webhooks + send messages is the `phone_number_id`.
    Access token is configured server-side via META_WHATSAPP_ACCESS_TOKEN.
    """

    phone_number_id = (payload.phone_number_id or "").strip()
    if not phone_number_id.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="phone_number_id must be a numeric string",
        )

    identifier = f"meta:{phone_number_id}"

    # Ensure uniqueness across all tenants for a given Meta phone_number_id
    existing_other = (
        db.query(Channel)
        .filter(Channel.type == "whatsapp", Channel.identifier == identifier, Channel.tenant_id != current_tenant.id)
        .first()
    )
    if existing_other:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Meta phone_number_id is already connected to another tenant",
        )

    # Prefer updating an existing whatsapp channel for this tenant
    existing = (
        db.query(Channel)
        .filter(Channel.tenant_id == current_tenant.id, Channel.type == "whatsapp")
        .order_by(Channel.created_at.asc())
        .first()
    )

    meta_info = {
        "provider": "meta",
        "phone_number_id": phone_number_id,
    }
    if payload.business_whatsapp_number:
        meta_info["business_whatsapp_number"] = payload.business_whatsapp_number

    if existing:
        existing.identifier = identifier
        existing.status = "active"
        existing.description = json.dumps(meta_info)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return MetaWhatsAppConnectResponse(
            success=True,
            message="Meta WhatsApp connected",
            channel_id=existing.id,
            identifier=existing.identifier,
        )

    channel = Channel(
        tenant_id=current_tenant.id,
        type="whatsapp",
        identifier=identifier,
        status="active",
        description=json.dumps(meta_info),
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    return MetaWhatsAppConnectResponse(
        success=True,
        message="Meta WhatsApp connected",
        channel_id=channel.id,
        identifier=channel.identifier,
    )


@router.get("/webhook")
def meta_webhook_verify(
    hub_mode: str | None = None,
    hub_challenge: str | None = None,
    hub_verify_token: str | None = None,
):
    """Meta webhook verification (GET).

    Meta calls with query params:
    - hub.mode
    - hub.challenge
    - hub.verify_token
    """

    # FastAPI maps query params with dots as underscores when passed explicitly.
    # But to keep it simple, also accept underscore style.
    if hub_mode != "subscribe":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid hub.mode")

    expected = settings.META_WHATSAPP_VERIFY_TOKEN
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="META_WHATSAPP_VERIFY_TOKEN is not configured",
        )

    if hub_verify_token != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid verify token")

    return PlainTextResponse(content=hub_challenge or "")


@router.post("/webhook")
async def meta_webhook_receive(request: Request, db: Session = Depends(get_db)):
    """Meta Cloud API webhook receiver.

    Receives inbound WhatsApp messages and auto-replies using tenant AI settings.
    """

    raw_body = await request.body()

    # Optional signature verification (recommended in production)
    if settings.META_APP_SECRET:
        sig = request.headers.get("X-Hub-Signature-256")
        if not verify_meta_signature(settings.META_APP_SECRET, raw_body, sig):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook signature")

    payload = await request.json()

    # Meta sends many event types. We only handle messages.
    entries = payload.get("entry") or []
    for entry in entries:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            phone_number_id = metadata.get("phone_number_id")
            if not phone_number_id:
                continue

            channel = (
                db.query(Channel)
                .filter(Channel.type == "whatsapp", Channel.identifier == f"meta:{phone_number_id}")
                .first()
            )
            if not channel:
                # Unknown phone_number_id -> ignore (still return 200 to Meta)
                continue

            tenant = db.query(Tenant).filter(Tenant.id == channel.tenant_id).first()
            if not tenant:
                continue

            messages = value.get("messages") or []
            for msg in messages:
                # Only handle text messages for now
                if msg.get("type") != "text":
                    continue

                from_wa = msg.get("from")
                text = (msg.get("text") or {}).get("body")
                if not from_wa or not text:
                    continue

                ai_reply, confidence = get_ai_response(
                    message_text=text,
                    ai_provider=tenant.ai_provider or "gemini",
                    system_prompt=tenant.ai_system_prompt or "",
                    model=getattr(tenant, "ai_model", None),
                    temperature=getattr(tenant, "ai_temperature", 0.7),
                )

                # Save incoming message
                incoming_msg = Message(
                    tenant_id=tenant.id,
                    channel_id=channel.id,
                    direction="incoming",
                    message_text=text,
                    ai_response=None,
                    confidence_score=None,
                    status="received",
                    escalated_to_human=False,
                    customer_contact=from_wa,
                )
                db.add(incoming_msg)

                access_token = settings.META_WHATSAPP_ACCESS_TOKEN
                if not access_token:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="META_WHATSAPP_ACCESS_TOKEN is not configured",
                    )

                await send_whatsapp_text_message(
                    access_token=access_token,
                    phone_number_id=str(phone_number_id),
                    to=str(from_wa),
                    message=str(ai_reply),
                    api_version=settings.META_GRAPH_API_VERSION,
                )

                # Save outgoing message
                outgoing_msg = Message(
                    tenant_id=tenant.id,
                    channel_id=channel.id,
                    direction="outgoing",
                    message_text=ai_reply,
                    ai_response=None,
                    confidence_score=confidence,
                    status="sent",
                    escalated_to_human=False,
                    customer_contact=from_wa,
                )
                db.add(outgoing_msg)

                db.commit()

    return {"success": True}