from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from auth.dependencies import get_current_tenant
from database import get_db
from models import Channel, Tenant
from config import settings
from schemas.twilio import PurchaseTwilioNumberRequest, PurchaseTwilioNumberResponse

router = APIRouter()


def _get_twilio_client() -> Client:
    sid = settings.TWILIO_ACCOUNT_SID
    token = settings.TWILIO_AUTH_TOKEN

    if not sid or not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twilio credentials are not configured (TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN)",
        )

    return Client(sid, token)


def _normalize_public_base_url(value: str) -> str:
    base = (value or "").strip()
    if not base:
        raise ValueError("Public base URL is empty")
    if not (base.startswith("http://") or base.startswith("https://")):
        raise ValueError("Public base URL must start with http:// or https://")
    return base.rstrip("/")


@router.get("/available-numbers")
def get_available_numbers(
    country: str = Query("US", min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code"),
    number_type: str = Query(
        "local",
        pattern="^(local|toll_free)$",
        description="Type of numbers to search: local or toll_free",
    ),
    limit: int = Query(20, ge=1, le=50),
    contains: Optional[str] = Query(None, description="Optional digits/pattern the phone number should contain"),
    region: Optional[str] = Query(None, description="Filter by region/state (where supported)"),
    locality: Optional[str] = Query(None, description="Filter by locality/city (where supported)"),
    sms_enabled: Optional[bool] = Query(True, description="Require SMS-capable numbers"),
    voice_enabled: Optional[bool] = Query(None, description="Optionally require Voice-capable numbers"),
    _: Tenant = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Return Twilio available phone numbers + rough location metadata.

    Requires an authenticated tenant (Bearer token) since this exposes account inventory/search.
    """

    client = _get_twilio_client()

    # Twilio expects uppercase ISO country codes
    country = country.upper()

    # Build kwargs, dropping None values (Twilio SDK doesn't like explicit None for some params)
    kwargs: Dict[str, Any] = {"limit": limit}
    if contains:
        kwargs["contains"] = contains
    if region:
        kwargs["in_region"] = region
    if locality:
        kwargs["in_locality"] = locality
    if sms_enabled is not None:
        kwargs["sms_enabled"] = sms_enabled
    if voice_enabled is not None:
        kwargs["voice_enabled"] = voice_enabled

    try:
        available = client.available_phone_numbers(country)

        if number_type == "local":
            numbers = available.local.list(**kwargs)
        else:
            numbers = available.toll_free.list(**kwargs)

        results: List[Dict[str, Any]] = []
        for n in numbers:
            # Fields vary by country/type; keep a stable core set.
            results.append(
                {
                    "phone_number": getattr(n, "phone_number", None),
                    "friendly_name": getattr(n, "friendly_name", None),
                    "iso_country": getattr(n, "iso_country", None),
                    "region": getattr(n, "region", None),
                    "locality": getattr(n, "locality", None),
                    "postal_code": getattr(n, "postal_code", None),
                    "rate_center": getattr(n, "rate_center", None),
                    "lata": getattr(n, "lata", None),
                    "latitude": getattr(n, "latitude", None),
                    "longitude": getattr(n, "longitude", None),
                }
            )

        return {"country": country, "type": number_type, "count": len(results), "results": results}

    except TwilioRestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Twilio error: {getattr(e, 'msg', str(e))}",
        )


@router.post("/purchase-number", response_model=PurchaseTwilioNumberResponse)
def purchase_number(
    payload: PurchaseTwilioNumberRequest,
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Purchase a Twilio phone number and configure SMS + Voice webhooks.

    Also creates `Channel` rows for the tenant:
    - type=sms, identifier=<phone_number>
    - type=voice, identifier=<phone_number>
    """

    client = _get_twilio_client()

    # Prefer explicit payload value, else env, else request base URL.
    raw_base = payload.webhook_base_url or settings.PUBLIC_WEBHOOK_BASE_URL or str(request.base_url)
    try:
        public_base_url = _normalize_public_base_url(raw_base)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    sms_url = f"{public_base_url}/api/sms/receive"
    voice_url = f"{public_base_url}/api/voice/receive"

    try:
        incoming = client.incoming_phone_numbers.create(
            phone_number=payload.phone_number,
            sms_url=sms_url,
            sms_method="POST",
            voice_url=voice_url,
            voice_method="POST",
        )

        # Defensive: ensure both webhooks are set even if Twilio partially applied create params.
        client.incoming_phone_numbers(incoming.sid).update(
            sms_url=sms_url,
            sms_method="POST",
            voice_url=voice_url,
            voice_method="POST",
        )
    except TwilioRestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Twilio error purchasing number: {getattr(e, 'msg', str(e))}",
        )

    created_sms_channel = False
    created_voice_channel = False

    # Create SMS channel if missing
    existing_sms = (
        db.query(Channel)
        .filter(
            Channel.tenant_id == current_tenant.id,
            Channel.type == "sms",
            Channel.identifier == payload.phone_number,
        )
        .first()
    )
    if not existing_sms:
        db.add(
            Channel(
                tenant_id=current_tenant.id,
                type="sms",
                identifier=payload.phone_number,
            )
        )
        created_sms_channel = True

    # Create Voice channel if missing
    existing_voice = (
        db.query(Channel)
        .filter(
            Channel.tenant_id == current_tenant.id,
            Channel.type == "voice",
            Channel.identifier == payload.phone_number,
        )
        .first()
    )
    if not existing_voice:
        db.add(
            Channel(
                tenant_id=current_tenant.id,
                type="voice",
                identifier=payload.phone_number,
            )
        )
        created_voice_channel = True

    db.commit()

    return PurchaseTwilioNumberResponse(
        success=True,
        phone_number=payload.phone_number,
        incoming_phone_number_sid=incoming.sid,
        sms_url=sms_url,
        voice_url=voice_url,
        created_sms_channel=created_sms_channel,
        created_voice_channel=created_voice_channel,
    )
