from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid


class BusinessHours(BaseModel):
    open_time: str
    close_time: str
    timezone: str


class FAQItem(BaseModel):
    question: str
    answer: str


class ServiceItem(BaseModel):
    service: str
    price: str


class ChannelInput(BaseModel):
    type: str
    identifier: str


class TenantSetupRequest(BaseModel):
    business_name: str
    industry: str
    phone_number: str
    channels: List[ChannelInput]
    greeting_message: str
    tone_of_voice: str
    business_hours: BusinessHours
    faq: List[FAQItem]
    services: List[ServiceItem]


class TenantSetupResponse(BaseModel):
    success: bool
    message: str
    tenant_id: uuid.UUID
    updated_fields: dict


class ChannelResponse(BaseModel):
    id: uuid.UUID
    type: str
    identifier: str
    status: str

    class Config:
        from_attributes = True