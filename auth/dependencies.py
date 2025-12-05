from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from models import Tenant
from auth.security import decode_token
from typing import Optional

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_tenant(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Tenant:
    """Get the current tenant from the JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_token(token)
        if payload is None:
            raise credentials_exception
            
        tenant_id: str = payload.get("tenant_id")
        tenant_email: str = payload.get("email")
        
        if tenant_id is None or tenant_email is None:
            raise credentials_exception
            
    except Exception:
        raise credentials_exception
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return tenant