from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import get_db
from models import Tenant, Channel
from auth.dependencies import get_current_tenant
from schemas.settings import TenantSettingsResponse, TenantSettingsUpdateRequest, SettingsChannelResponse

router = APIRouter()


def _build_settings_response(db: Session, tenant: Tenant) -> TenantSettingsResponse:
    channels = db.query(Channel).filter(Channel.tenant_id == tenant.id).order_by(Channel.created_at.asc()).all()

    return TenantSettingsResponse(
        id=tenant.id,
        business_name=tenant.business_name,
        email=tenant.email,
        primary_phone=tenant.primary_phone,
        timezone=tenant.timezone,
        open_time=tenant.open_time,
        close_time=tenant.close_time,
        ai_provider=tenant.ai_provider or "gemini",
        ai_system_prompt=tenant.ai_system_prompt,
        escalation_phone=tenant.escalation_phone,
        plan=tenant.plan,
        subscription_status=tenant.subscription_status,
        onboarding_completed=bool(getattr(tenant, "onboarding_completed", False)),
        is_active=bool(getattr(tenant, "is_active", True)),
        created_at=tenant.created_at,
        updated_at=getattr(tenant, "updated_at", None),
        channels=[
            SettingsChannelResponse(
                id=ch.id,
                type=ch.type,  # type: ignore[arg-type]
                identifier=ch.identifier,
                status=ch.status,
                description=ch.description,
            )
            for ch in channels
            if ch.type in {"sms", "email", "chat", "voice"}
        ],
    )


@router.get("", response_model=TenantSettingsResponse)
def get_settings(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Return tenant settings + channels for Settings page."""
    try:
        return _build_settings_response(db, current_tenant)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to retrieve settings",
        )


@router.put("", response_model=TenantSettingsResponse)
def update_settings(
    payload: TenantSettingsUpdateRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Update tenant settings fields (tenant-based). Email/password/faqs/services handled elsewhere."""
    try:
        data = payload.model_dump(exclude_unset=True)

        # Apply updates only for allowed fields
        for field_name, value in data.items():
            setattr(current_tenant, field_name, value)

        db.add(current_tenant)
        db.commit()
        db.refresh(current_tenant)

        return _build_settings_response(db, current_tenant)

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to update settings",
        )
