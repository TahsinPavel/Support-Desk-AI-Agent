from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database import get_db
from models import Tenant
from schemas.subscription import (
    ActivateSubscriptionRequest,
    ActivateSubscriptionResponse,
    WebhookResponse
)
from datetime import datetime
from typing import Optional
import hashlib
import hmac
import json
import logging

router = APIRouter()

# Configure logging for webhook events
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Paddle webhook secret (should be in config/env)
import os
PADDLE_WEBHOOK_SECRET = os.getenv("PADDLE_WEBHOOK_SECRET", "")


# ==========================================
# Helper: Verify Paddle Signature
# ==========================================
def verify_paddle_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    """
    Verify Paddle webhook signature.
    Paddle uses HMAC-SHA256 for webhook verification.
    """
    if not secret:
        logger.warning("PADDLE_WEBHOOK_SECRET not configured - skipping signature verification")
        return True  # Skip verification if no secret configured

    try:
        # Paddle signature format: ts=timestamp;h1=hash
        parts = dict(part.split("=") for part in signature.split(";"))
        timestamp = parts.get("ts", "")
        received_hash = parts.get("h1", "")

        # Create signed payload
        signed_payload = f"{timestamp}:{payload.decode('utf-8')}"

        # Calculate expected hash
        expected_hash = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_hash, received_hash)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


# ==========================================
# 1️⃣ POST /subscription/activate
# ==========================================
@router.post("/activate", response_model=ActivateSubscriptionResponse)
def activate_subscription(
    request: ActivateSubscriptionRequest,
    db: Session = Depends(get_db)
):
    """
    Activate a subscription for a tenant.
    Called after successful Paddle checkout.
    """
    try:
        # Find tenant by email
        tenant = db.query(Tenant).filter(Tenant.email == request.email).first()

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant with email {request.email} not found"
            )

        # Check for duplicate subscription_id (different tenant)
        existing = db.query(Tenant).filter(
            Tenant.paddle_subscription_id == request.paddle_subscription_id,
            Tenant.id != tenant.id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Subscription ID already assigned to another tenant"
            )

        # Update tenant subscription info
        tenant.plan = request.plan
        tenant.subscription_status = "active"
        tenant.paddle_customer_id = request.paddle_customer_id
        tenant.paddle_subscription_id = request.paddle_subscription_id
        tenant.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(tenant)

        logger.info(f"Subscription activated for tenant {tenant.id} - Plan: {request.plan}")

        return ActivateSubscriptionResponse(
            success=True,
            message="Subscription activated",
            tenant_id=str(tenant.id),
            plan=request.plan
        )

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error activating subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to activate subscription"
        )


# ==========================================
# 2️⃣ POST /webhooks/paddle
# ==========================================
@router.post("/webhooks/paddle", response_model=WebhookResponse)
async def paddle_webhook(
    request: Request,
    paddle_signature: Optional[str] = Header(None, alias="Paddle-Signature"),
    db: Session = Depends(get_db)
):
    """
    Handle Paddle webhook events.
    Processes subscription lifecycle events.
    """
    try:
        # Get raw payload for signature verification
        payload = await request.body()

        # Parse JSON payload
        try:
            event_data = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload"
            )

        event_type = event_data.get("event_type", "")
        data = event_data.get("data", {})

        logger.info(f"Processing Paddle event: {event_type}")
        logger.info(f"Event data: {json.dumps(data, indent=2)}")

        # Extract subscription info from event data
        subscription_id = data.get("id") or data.get("subscription_id")
        customer_id = data.get("customer_id")
        subscription_status = data.get("status")

        # Also check nested custom_data for email
        custom_data = data.get("custom_data", {}) or {}
        tenant_email = custom_data.get("email")

        # Find tenant by paddle_subscription_id or email
        tenant = None
        if subscription_id:
            tenant = db.query(Tenant).filter(
                Tenant.paddle_subscription_id == subscription_id
            ).first()

        if not tenant and customer_id:
            tenant = db.query(Tenant).filter(
                Tenant.paddle_customer_id == customer_id
            ).first()

        if not tenant and tenant_email:
            tenant = db.query(Tenant).filter(
                Tenant.email == tenant_email
            ).first()

        # ==========================================
        # Handle different event types
        # ==========================================

        if event_type == "subscription.created":
            if tenant:
                tenant.subscription_status = "active"
                if subscription_id:
                    tenant.paddle_subscription_id = subscription_id
                if customer_id:
                    tenant.paddle_customer_id = customer_id
                tenant.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Subscription created for tenant {tenant.id}")
            else:
                logger.warning(f"subscription.created: Tenant not found for subscription {subscription_id}")

        elif event_type == "subscription.updated":
            if tenant:
                # Check if status changed
                if subscription_status:
                    tenant.subscription_status = subscription_status
                tenant.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Subscription updated for tenant {tenant.id} - Status: {subscription_status}")
            else:
                logger.warning(f"subscription.updated: Tenant not found for subscription {subscription_id}")

        elif event_type == "subscription.canceled":
            if tenant:
                tenant.subscription_status = "canceled"
                tenant.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Subscription canceled for tenant {tenant.id}")
            else:
                logger.warning(f"subscription.canceled: Tenant not found for subscription {subscription_id}")

        elif event_type == "subscription.paused":
            if tenant:
                tenant.subscription_status = "paused"
                tenant.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Subscription paused for tenant {tenant.id}")

        elif event_type == "subscription.resumed":
            if tenant:
                tenant.subscription_status = "active"
                tenant.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Subscription resumed for tenant {tenant.id}")

        elif event_type in ["transaction.completed", "transaction.paid"]:
            # Payment successful - ensure subscription is active
            if tenant:
                tenant.subscription_status = "active"
                tenant.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Payment received for tenant {tenant.id}")

        elif event_type == "subscription.past_due":
            if tenant:
                tenant.subscription_status = "past_due"
                tenant.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Subscription past due for tenant {tenant.id}")

        else:
            logger.info(f"Unhandled Paddle event type: {event_type}")

        return WebhookResponse(
            success=True,
            message=f"Webhook processed: {event_type}"
        )

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error processing webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error processing webhook"
        )
    except Exception as e:
        logger.error(f"Error processing Paddle webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing webhook"
        )


# ==========================================
# 3️⃣ GET /subscription/status (bonus)
# ==========================================
@router.get("/status")
def get_subscription_status(
    email: str,
    db: Session = Depends(get_db)
):
    """
    Get subscription status for a tenant by email.
    """
    tenant = db.query(Tenant).filter(Tenant.email == email).first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    return {
        "tenant_id": str(tenant.id),
        "email": tenant.email,
        "plan": tenant.plan,
        "subscription_status": tenant.subscription_status,
        "paddle_customer_id": tenant.paddle_customer_id,
        "paddle_subscription_id": tenant.paddle_subscription_id
    }
