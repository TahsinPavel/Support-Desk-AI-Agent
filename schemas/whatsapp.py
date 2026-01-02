from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional


class WhatsAppConnectRequest(BaseModel):
    whatsapp_number: str = Field(
        ..., description="Business WhatsApp phone number in E.164 format", examples=["+14155550123"]
    )


class WhatsAppConnectResponse(BaseModel):
    success: bool
    message: str
    channel_id: UUID
    identifier: str


class MetaWhatsAppConnectRequest(BaseModel):
    phone_number_id: str = Field(
        ..., description="Meta WhatsApp Cloud API phone_number_id", examples=["123456789012345"]
    )
    business_whatsapp_number: Optional[str] = Field(
        None,
        description="Optional business WhatsApp number in E.164 (for display only)",
        examples=["+14155550123"],
    )


class MetaWhatsAppConnectResponse(BaseModel):
    success: bool
    message: str
    channel_id: UUID
    identifier: str
