from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Literal, Optional
import httpx

from auth.dependencies import get_current_tenant
from config import settings
from schemas.pricing import PricingPlan, PricingPlansResponse, PlanKey
from models import Tenant


router = APIRouter()


def _paddle_base_url() -> str:
    env = (settings.PADDLE_ENVIRONMENT or "sandbox").lower()
    if env == "production":
        return "https://api.paddle.com"
    return "https://sandbox-api.paddle.com"


def _get_plan_catalog() -> list[PricingPlan]:
    return [
        PricingPlan(
            key="starter",
            name="Starter AI",
            price_usd=149,
            billing_period="month",
            is_active=True,
            is_available_soon=False,
            paddle_price_id=settings.PADDLE_STARTER_PRICE_ID,
        ),
        PricingPlan(
            key="growth",
            name="Growth AI",
            price_usd=None,
            billing_period="month",
            is_active=False,
            is_available_soon=True,
            paddle_price_id=settings.PADDLE_GROWTH_PRICE_ID,
        ),
        PricingPlan(
            key="enterprise",
            name="Enterprise AI",
            price_usd=None,
            billing_period="month",
            is_active=False,
            is_available_soon=True,
            paddle_price_id=settings.PADDLE_ENTERPRISE_PRICE_ID,
        ),
    ]


@router.get("/plans", response_model=PricingPlansResponse)
def get_plans() -> PricingPlansResponse:
    """Frontend pricing page plan list."""
    return PricingPlansResponse(plans=_get_plan_catalog())


class CreateCheckoutRequest(BaseModel):
    plan: PlanKey = Field(..., description="Plan to purchase")
    success_url: Optional[str] = Field(None, description="Override success URL")
    cancel_url: Optional[str] = Field(None, description="Override cancel URL")


class CreateCheckoutResponse(BaseModel):
    checkout_url: str
    transaction_id: Optional[str] = None


@router.post("/checkout", response_model=CreateCheckoutResponse)
async def create_checkout(
    body: CreateCheckoutRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
) -> CreateCheckoutResponse:
    """Creates a Paddle hosted checkout link for the selected plan.

    This uses Paddle Billing API and requires server-side `PADDLE_API_KEY`.
    """

    plans = {p.key: p for p in _get_plan_catalog()}
    plan = plans.get(body.plan)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan")

    if not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan is not currently available",
        )

    if not plan.paddle_price_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paddle price id is not configured for this plan",
        )

    if not settings.PADDLE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PADDLE_API_KEY is not configured",
        )

    frontend_url = settings.FRONTEND_URL or ""
    success_url = body.success_url or (frontend_url.rstrip("/") + "/billing/success")
    cancel_url = body.cancel_url or (frontend_url.rstrip("/") + "/billing/cancel")

    # Paddle Billing: create a transaction with a hosted checkout URL.
    # If your Paddle account uses a different endpoint/shape, share a sample and I’ll adapt.
    payload = {
        "items": [{"price_id": plan.paddle_price_id, "quantity": 1}],
        "customer": {"email": current_tenant.email},
        "custom_data": {
            "tenant_id": str(current_tenant.id),
            "email": current_tenant.email,
            "plan": plan.key,
        },
        "checkout": {
            "settings": {
                "success_url": success_url,
                "cancel_url": cancel_url,
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {settings.PADDLE_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{_paddle_base_url()}/transactions", json=payload, headers=headers)

    if resp.status_code >= 400:
        # Return a safe-ish payload for debugging without leaking secrets.
        try:
            err = resp.json()
        except Exception:
            err = {"raw": resp.text}
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "Paddle API error", "status": resp.status_code, "error": err},
        )

    data = resp.json()
    transaction_id = (data.get("data") or {}).get("id") if isinstance(data, dict) else None

    # Paddle typically returns a checkout URL nested in `data.checkout.url`.
    checkout_url = None
    if isinstance(data, dict):
        checkout = (data.get("data") or {}).get("checkout") or {}
        checkout_url = checkout.get("url")

    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "Paddle response missing checkout URL", "response": data},
        )

    return CreateCheckoutResponse(checkout_url=checkout_url, transaction_id=transaction_id)
