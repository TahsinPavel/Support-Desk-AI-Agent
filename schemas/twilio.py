from pydantic import BaseModel, Field
from typing import Optional


class PurchaseTwilioNumberRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number to purchase (E.164)", examples=["+14155552671"])
    webhook_base_url: Optional[str] = Field(
        None,
        description=(
            "Public base URL that Twilio can reach (e.g. https://<your-domain>). "
            "If omitted, uses PUBLIC_WEBHOOK_BASE_URL from env, else falls back to the request base URL."
        ),
        examples=["https://api.example.com"],
    )


class PurchaseTwilioNumberResponse(BaseModel):
    success: bool
    phone_number: str
    incoming_phone_number_sid: str
    sms_url: str
    voice_url: str
    created_sms_channel: bool
    created_voice_channel: bool
