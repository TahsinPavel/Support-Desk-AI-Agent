import hmac
import hashlib
from typing import Optional

import httpx


def verify_meta_signature(app_secret: str, body: bytes, signature_header: Optional[str]) -> bool:
    """Verify Meta webhook signature (X-Hub-Signature-256).

    Header format: "sha256=<hex>"
    """
    if not app_secret or not signature_header:
        return False

    if not signature_header.startswith("sha256="):
        return False

    provided = signature_header.split("=", 1)[1].strip()
    expected = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided, expected)


async def send_whatsapp_text_message(
    *,
    access_token: str,
    phone_number_id: str,
    to: str,
    message: str,
    api_version: str = "v19.0",
) -> None:
    url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message},
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
