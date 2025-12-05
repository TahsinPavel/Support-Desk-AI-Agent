from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date, or_
from sqlalchemy.exc import SQLAlchemyError
from database import get_db
from models import Tenant, Appointment
from auth.dependencies import get_current_tenant
from schemas.appointments import (
    AppointmentResponse,
    AppointmentListResponse,
    AppointmentSummaryResponse,
    AppointmentCreate,
    AppointmentUpdate,
    TrendItem
)
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import uuid as uuid_module

router = APIRouter()


# ==========================================
# Helper: Convert Appointment to Response
# ==========================================
def appointment_to_response(apt: Appointment) -> AppointmentResponse:
    """Convert SQLAlchemy Appointment model to Pydantic response."""
    return AppointmentResponse(
        id=str(apt.id),
        customer_name=apt.customer_name,
        customer_contact=apt.customer_contact,
        service=apt.service,
        requested_time=apt.requested_time,
        confirmed_time=apt.confirmed_time,
        status=apt.status or "pending",
        notes=apt.notes,
        ai_conversation=apt.ai_conversation,
        created_at=apt.created_at,
        updated_at=apt.updated_at
    )


# ==========================================
# 1️⃣ GET /appointments — List + Filters
# ==========================================
@router.get("", response_model=AppointmentListResponse)
def get_appointments(
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    status: Optional[str] = Query(None, pattern="^(pending|confirmed|completed|canceled)$"),
    service: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search by customer name or contact"),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Get all appointments for the authenticated tenant with optional filters.
    """
    try:
        query = db.query(Appointment).filter(
            Appointment.tenant_id == current_tenant.id
        )

        # Apply filters
        if start_date:
            query = query.filter(Appointment.created_at >= start_date)
        if end_date:
            query = query.filter(Appointment.created_at <= end_date)
        if status:
            query = query.filter(Appointment.status == status)
        if service:
            query = query.filter(Appointment.service.ilike(f"%{service}%"))
        if search:
            query = query.filter(
                or_(
                    Appointment.customer_name.ilike(f"%{search}%"),
                    Appointment.customer_contact.ilike(f"%{search}%")
                )
            )

        # Order by created_at DESC
        appointments = query.order_by(Appointment.created_at.desc()).all()

        return AppointmentListResponse(
            appointments=[appointment_to_response(apt) for apt in appointments],
            total=len(appointments)
        )

    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to retrieve appointments"
        )


# ==========================================
# 2️⃣ GET /appointments/summary — Stats
# ==========================================
@router.get("/summary", response_model=AppointmentSummaryResponse)
def get_appointment_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days for stats"),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Get appointment summary statistics for the specified number of days.
    """
    try:
        tenant_id = current_tenant.id
        today = datetime.utcnow().date()
        start_date = today - timedelta(days=days - 1)

        # Base query for date range
        base_query = db.query(Appointment).filter(
            Appointment.tenant_id == tenant_id,
            cast(Appointment.created_at, Date) >= start_date,
            cast(Appointment.created_at, Date) <= today
        )

        # Count by status
        total = base_query.count()
        pending = base_query.filter(Appointment.status == "pending").count()
        confirmed = base_query.filter(Appointment.status == "confirmed").count()
        completed = base_query.filter(Appointment.status == "completed").count()
        canceled = base_query.filter(Appointment.status == "canceled").count()

        # Trend: group by day
        daily_counts = db.query(
            cast(Appointment.created_at, Date).label('day'),
            func.count(Appointment.id).label('count')
        ).filter(
            Appointment.tenant_id == tenant_id,
            cast(Appointment.created_at, Date) >= start_date,
            cast(Appointment.created_at, Date) <= today
        ).group_by(
            cast(Appointment.created_at, Date)
        ).order_by(
            cast(Appointment.created_at, Date)
        ).all()

        # Create dict for lookup
        counts_dict = {str(row.day): row.count for row in daily_counts}

        # Build full trend with 0 for missing days
        trend = []
        for i in range(days):
            day = start_date + timedelta(days=i)
            day_str = str(day)
            trend.append(TrendItem(date=day_str, count=counts_dict.get(day_str, 0)))

        return AppointmentSummaryResponse(
            total=total,
            pending=pending,
            confirmed=confirmed,
            completed=completed,
            canceled=canceled,
            trend=trend
        )

    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to retrieve summary"
        )


# ==========================================
# 3️⃣ GET /appointments/{id} — Single Appointment
# ==========================================
@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Get a single appointment by ID.
    Returns full details including AI conversation and notes.
    """
    try:
        appointment = db.query(Appointment).filter(
            Appointment.id == appointment_id,
            Appointment.tenant_id == current_tenant.id
        ).first()

        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )

        return appointment_to_response(appointment)

    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to retrieve appointment"
        )


# ==========================================
# 4️⃣ PUT /appointments/{id} — Update Appointment
# ==========================================
@router.put("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: UUID,
    update_data: AppointmentUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Update an existing appointment.
    Only updates fields that are provided in the request.
    """
    try:
        appointment = db.query(Appointment).filter(
            Appointment.id == appointment_id,
            Appointment.tenant_id == current_tenant.id
        ).first()

        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )

        # Update only provided fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if value is not None:
                setattr(appointment, field, value)

        appointment.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(appointment)

        return appointment_to_response(appointment)

    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to update appointment"
        )


# ==========================================
# 5️⃣ POST /appointments — Create Appointment
# ==========================================
@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    appointment_data: AppointmentCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Create a new appointment for the authenticated tenant.
    """
    try:
        now = datetime.utcnow()

        appointment = Appointment(
            id=uuid_module.uuid4(),
            tenant_id=current_tenant.id,
            channel_id=None,  # Can be set later if needed
            customer_name=appointment_data.customer_name,
            customer_contact=appointment_data.customer_contact,
            service=appointment_data.service,
            requested_time=appointment_data.requested_time,
            confirmed_time=appointment_data.confirmed_time,
            status=appointment_data.status or "pending",
            notes=appointment_data.notes,
            ai_conversation=None,
            created_at=now,
            updated_at=now
        )

        db.add(appointment)
        db.commit()
        db.refresh(appointment)

        return appointment_to_response(appointment)

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Failed to create appointment"
        )
