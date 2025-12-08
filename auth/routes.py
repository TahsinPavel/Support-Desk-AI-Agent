from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import get_db
from models import Tenant
from schemas import auth
from auth import security
from auth import dependencies
from datetime import timedelta
import uuid

router = APIRouter(tags=["Authentication"])

# Token expiration times
ACCESS_TOKEN_EXPIRE_MINUTES = 60


@router.post("/signup", response_model=auth.TokenResponse)
def signup(tenant_data: auth.TenantSignupRequest, db: Session = Depends(get_db)):
    """Register a new tenant."""
    # Check if tenant with this email already exists
    existing_tenant = db.query(Tenant).filter(Tenant.email == tenant_data.email).first()
    if existing_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash the password
    hashed_password = security.hash_password(tenant_data.password)
    
    # Create new tenant
    new_tenant = Tenant(
        id=uuid.uuid4(),
        business_name=tenant_data.business_name,
        email=tenant_data.email,
        hashed_password=hashed_password,
        primary_phone=tenant_data.primary_phone,
        timezone=tenant_data.timezone or "UTC",
        plan="starter",  # Default plan
        subscription_status="active"  # Default status
    )
    
    try:
        db.add(new_tenant)
        db.commit()
        db.refresh(new_tenant)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={
            "tenant_id": str(new_tenant.id),
            "email": new_tenant.email,
            "plan": new_tenant.plan
        },
        expires_delta=access_token_expires
    )
    
    # Return token and tenant info
    return auth.TokenResponse(
        access_token=access_token,
        token_type="bearer",
        tenant=auth.TenantResponse.from_orm(new_tenant)
    )


@router.post("/login", response_model=auth.TokenResponse)
def login(credentials: auth.TenantLoginRequest, db: Session = Depends(get_db)):
    """Authenticate a tenant and return a JWT token."""
    # Find tenant by email
    tenant = db.query(Tenant).filter(Tenant.email == credentials.email).first()
    
    # Check if tenant exists and password is correct
    if not tenant or not security.verify_password(credentials.password, tenant.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Check if tenant is active
    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={
            "tenant_id": str(tenant.id),
            "email": tenant.email,
            "plan": tenant.plan
        },
        expires_delta=access_token_expires
    )
    
    # Return token and tenant info
    return auth.TokenResponse(
        access_token=access_token,
        token_type="bearer",
        tenant=auth.TenantResponse.from_orm(tenant)
    )


@router.get("/me", response_model=auth.TenantResponse)
def get_me(current_tenant: Tenant = Depends(dependencies.get_current_tenant)):
    """Return the current authenticated tenant's profile."""
    return auth.TenantResponse.from_orm(current_tenant)


@router.post("/logout")
def logout():
    """Logout endpoint (token revocation placeholder)."""
    # In a more advanced implementation, you might want to implement token blacklisting
    # For now, we'll just return a success message
    return {"message": "Successfully logged out"}