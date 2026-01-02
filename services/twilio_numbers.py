from typing import Optional, Tuple

from fastapi import HTTPException, status
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from config import settings


def _normalize_public_base_url(value: str) -> str:
    base = (value or "").strip()
    if not base:
        raise ValueError("Public base URL is empty")
    if not (base.startswith("http://") or base.startswith("https://")):
        raise ValueError("Public base URL must start with http:// or https://")
    return base.rstrip("/")


def get_twilio_client() -> Client:
    sid = settings.TWILIO_ACCOUNT_SID
    token = settings.TWILIO_AUTH_TOKEN
    if not sid or not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twilio credentials are not configured (TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN)",
        )
    return Client(sid, token)


def build_webhook_urls(public_base_url: str) -> Tuple[str, str]:
    base = _normalize_public_base_url(public_base_url)
    return f"{base}/api/sms/receive", f"{base}/api/voice/receive"


def ensure_incoming_number_with_webhooks(
    *,
    client: Client,
    phone_number: str,
    public_base_url: str,
) -> Tuple[str, str, str]:
    """Ensure a Twilio IncomingPhoneNumber exists for phone_number and has SMS + Voice webhooks set.

    Returns: (incoming_phone_number_sid, sms_url, voice_url)
    """

    sms_url, voice_url = build_webhook_urls(public_base_url)

    try:
        existing = client.incoming_phone_numbers.list(phone_number=phone_number, limit=1)
        if existing:
            incoming = existing[0]
            client.incoming_phone_numbers(incoming.sid).update(
                sms_url=sms_url,
                sms_method="POST",
                voice_url=voice_url,
                voice_method="POST",
            )
            return incoming.sid, sms_url, voice_url

        incoming = client.incoming_phone_numbers.create(
            phone_number=phone_number,
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

        return incoming.sid, sms_url, voice_url

    except TwilioRestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Twilio error: {getattr(e, 'msg', str(e))}",
        )
