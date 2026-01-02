from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from twilio.rest import Client
from twilio.base.exceptions import TwilioException, TwilioRestException
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


def _discover_supported_number_types(
    client: Client,
    country: str,
    sms_enabled: Optional[bool] = None,
    voice_enabled: Optional[bool] = None,
) -> List[str]:
    """Probe Twilio to determine which number_type resources exist for a country.

    Twilio returns HTTP 404 for unavailable resources like /AvailablePhoneNumbers/{CC}/Local.json.
    We use a tiny request (limit=1) to test each type.
    """

    supported: List[str] = []
    available = client.available_phone_numbers(country)
    candidate_types = ["local", "toll_free", "mobile", "national", "shared_cost"]

    for t in candidate_types:
        resource = getattr(available, t, None)
        if resource is None:
            continue

        kwargs: Dict[str, Any] = {"limit": 1}
        if sms_enabled is not None:
            kwargs["sms_enabled"] = sms_enabled
        if voice_enabled is not None:
            kwargs["voice_enabled"] = voice_enabled

        try:
            resource.list(**kwargs)
            supported.append(t)
        except TwilioException:
            continue

    return supported


@router.get("/available-numbers")
def get_available_numbers(
    country: str = Query(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code"),
    number_type: str = Query(
        "local",
        pattern="^(local|toll_free|mobile|national|shared_cost)$",
        description="Type of numbers to search: local, toll_free, mobile, national, shared_cost",
    ),
    max_numbers_scanned: int = Query(
        5000,
        ge=1,
        le=5000,
        description="Safety cap: how many available numbers to scan from Twilio",
    ),
    contains: Optional[str] = Query(None, description="Optional digits/pattern the phone number should contain"),
    region: Optional[str] = Query(None, description="Filter by region/state (where supported)"),
    locality: Optional[str] = Query(None, description="Filter by locality/city (where supported)"),
    sms_enabled: Optional[bool] = Query(None, description="If set, filter by SMS-capable numbers"),
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
    kwargs: Dict[str, Any] = {}
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

        results: List[Dict[str, Any]] = []
        scanned = 0

        number_resource = getattr(available, number_type, None)
        if number_resource is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Number type '{number_type}' is not supported for country '{country}'",
            )

        for n in number_resource.stream(limit=max_numbers_scanned, **kwargs):
            scanned += 1
            # Fields vary by country/type; keep a stable core set.
            results.append(
                {
                    "phone_number": getattr(n, "phone_number", None),
                    "friendly_name": getattr(n, "friendly_name", None),
                    "iso_country": getattr(n, "iso_country", None),
                    "region": getattr(n, "region", None),
                    "locality": getattr(n, "locality", None),
                    "postal_code": getattr(n, "postal_code", None),
                }
            )

        return {
            "country": country,
            "type": number_type,
            "scanned": scanned,
            "count": len(results),
            "results": results,
            "truncated": scanned >= max_numbers_scanned,
        }

    except (TwilioRestException, TwilioException) as e:
        message = getattr(e, "msg", str(e))
        # Countries can return 404 for unsupported number type endpoints (e.g. IT/Local.json).
        if "HTTP 404" in message or "20404" in message:
            supported_types = _discover_supported_number_types(
                client,
                country,
                sms_enabled=sms_enabled,
                voice_enabled=voice_enabled,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": f"No '{number_type}' numbers endpoint is available for country '{country}'.",
                    "supported_number_types": supported_types,
                },
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Twilio error: {message}",
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


@router.get("/locations")
def get_locations(
    country: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code. If omitted, returns available countries.",
    ),
    number_type: str = Query(
        "local",
        pattern="^(local|toll_free|mobile|national|shared_cost)$",
        description="Type of numbers to search: local, toll_free, mobile, national, shared_cost",
    ),
    region: Optional[str] = Query(
        None,
        description=(
            "If provided, returns localities for this region/state; "
            "if omitted, returns regions/states for the country."
        ),
    ),
    countries_limit: int = Query(
        500,
        ge=1,
        le=5000,
        description="When country is omitted, max countries to return (safety cap)",
    ),
    max_unique: int = Query(
        5000,
        ge=1,
        le=10000,
        description="Safety cap: stop after collecting this many unique regions/localities",
    ),
    max_numbers_scanned: int = Query(
        5000,
        ge=1,
        le=5000,
        description="Safety cap: how many available numbers to scan from Twilio",
    ),
    sms_enabled: Optional[bool] = Query(None, description="If set, filter by SMS-capable numbers"),
    voice_enabled: Optional[bool] = Query(None, description="Optionally require Voice-capable numbers"),
    _: Tenant = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """Dynamically derive regions/localities for a country from Twilio available numbers.

    If `country` is omitted, returns the available countries list from Twilio.

    - If `region` is NOT provided: returns unique regions/states.
    - If `region` IS provided: returns unique localities/cities within that region.

    Notes:
    - Twilio doesn't provide a standalone canonical list endpoint for every country.
      This endpoint queries available numbers and aggregates distinct values.
    - Results depend on what Twilio returns and the scan limits.
    """

    client = _get_twilio_client()

    # If caller didn't specify a country, return Twilio's available countries list.
    if not country:
        try:
            countries_iter = client.available_phone_numbers.stream(limit=countries_limit)
            results: List[Dict[str, Any]] = []
            for c in countries_iter:
                results.append(
                    {
                        "iso_country": getattr(c, "country_code", None),
                        "country": getattr(c, "country", None),
                    }
                )
            return {
                "count": len(results),
                "countries": results,
                "truncated": len(results) >= countries_limit,
            }
        except TwilioRestException as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Twilio error: {getattr(e, 'msg', str(e))}",
            )

    country = country.upper()

    kwargs: Dict[str, Any] = {}
    if region:
        kwargs["in_region"] = region
    if sms_enabled is not None:
        kwargs["sms_enabled"] = sms_enabled
    if voice_enabled is not None:
        kwargs["voice_enabled"] = voice_enabled

    try:
        available = client.available_phone_numbers(country)
        number_resource = getattr(available, number_type, None)
        if number_resource is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Number type '{number_type}' is not supported for country '{country}'",
            )

        scanned = 0

        if region:
            # Region provided => return localities for that region
            uniques: set[str] = set()
            for n in number_resource.stream(limit=max_numbers_scanned, **kwargs):
                scanned += 1
                value = getattr(n, "locality", None)
                if isinstance(value, str) and value.strip():
                    uniques.add(value.strip())
                    if len(uniques) >= max_unique:
                        break

            items = sorted(uniques)
            return {
                "country": country,
                "type": number_type,
                "region": region,
                "scanned": scanned,
                "count": len(items),
                "localities": items,
                "truncated": scanned >= max_numbers_scanned or len(items) >= max_unique,
            }

        # No region provided => attempt to return regions for the country.
        # For many countries Twilio doesn't populate `region`. In that case we fall back to localities.
        regions: set[str] = set()
        localities: set[str] = set()

        for n in number_resource.stream(limit=max_numbers_scanned, **kwargs):
            scanned += 1
            reg = getattr(n, "region", None)
            loc = getattr(n, "locality", None)

            if isinstance(reg, str) and reg.strip():
                regions.add(reg.strip())
            if isinstance(loc, str) and loc.strip():
                localities.add(loc.strip())

            if len(regions) >= max_unique or len(localities) >= max_unique:
                break

        if regions:
            items = sorted(regions)
            return {
                "country": country,
                "type": number_type,
                "scanned": scanned,
                "count": len(items),
                "regions": items,
                "truncated": scanned >= max_numbers_scanned or len(items) >= max_unique,
                "supports_regions": True,
            }

        # Fallback for locality-only countries
        items = sorted(localities)
        return {
            "country": country,
            "type": number_type,
            "scanned": scanned,
            "count": len(items),
            "localities": items,
            "truncated": scanned >= max_numbers_scanned or len(items) >= max_unique,
            "supports_regions": False,
        }

    except (TwilioRestException, TwilioException) as e:
        message = getattr(e, "msg", str(e))
        if "HTTP 404" in message or "20404" in message:
            supported_types = _discover_supported_number_types(
                client,
                country,
                sms_enabled=sms_enabled,
                voice_enabled=voice_enabled,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": f"No '{number_type}' numbers endpoint is available for country '{country}'.",
                    "supported_number_types": supported_types,
                },
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Twilio error: {message}",
        )
