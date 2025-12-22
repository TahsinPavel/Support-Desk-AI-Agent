from pydantic import BaseModel, Field
from typing import Literal, Optional


PlanKey = Literal["starter", "growth", "enterprise"]


class PricingPlan(BaseModel):
    key: PlanKey
    name: str
    price_usd: Optional[int] = Field(default=None, description="Monthly price in USD")
    billing_period: Optional[Literal["month"]] = "month"
    is_active: bool
    is_available_soon: bool
    paddle_price_id: Optional[str] = None


class PricingPlansResponse(BaseModel):
    plans: list[PricingPlan]
