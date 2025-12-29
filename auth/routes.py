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
import os
from datetime import datetime
from urllib.parse import urlencode
import httpx
from jose import jwt, JWTError
from google.oauth2 import id_token as google_id_token
from google.auth.transport.requests import Request as GoogleAuthRequest
from config import settings
import base64
import hashlib

router = APIRouter(tags=["Authentication"])

# Token expiration times
ACCESS_TOKEN_EXPIRE_MINUTES = 60


GOOGLE_AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = "openid email profile"


def _require_google_oauth_config() -> tuple[str, str]:
    client_id = settings.GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID")
    client_secret = settings.GOOGLE_CLIENT_SECRET or os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        missing: list[str] = []
        if not client_id:
            missing.append("GOOGLE_CLIENT_ID")
        if not client_secret:
            missing.append("GOOGLE_CLIENT_SECRET")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google OAuth is not configured (missing: {', '.join(missing)}).",
        )
    return client_id, client_secret


def _require_google_client_id() -> str:
    client_id = settings.GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured (missing: GOOGLE_CLIENT_ID).",
        )
    return client_id


def _login_or_signup_from_google_claims(
    *,
    db: Session,
    claims: dict,
    business_name: str | None,
    primary_phone: str | None,
    timezone: str | None,
) -> Tenant:
    email = claims.get("email")
    email_verified = claims.get("email_verified")
    google_sub = claims.get("sub")

    if not email or not google_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google profile missing required fields.",
        )

    if email_verified is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google email is not verified.",
        )

    tenant = db.query(Tenant).filter(Tenant.email == email).first()
    if tenant:
        if not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if tenant.google_sub and tenant.google_sub != google_sub:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already linked to a different Google account.",
            )

        if not tenant.google_sub:
            tenant.google_sub = google_sub
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
        return tenant

    derived_name = claims.get("name") or email.split("@")[0]
    final_business_name = (business_name or derived_name).strip() if (business_name or derived_name) else derived_name
    if not final_business_name:
        final_business_name = derived_name

    new_tenant = Tenant(
        id=uuid.uuid4(),
        business_name=final_business_name,
        email=email,
        hashed_password=security.hash_password(uuid.uuid4().hex + uuid.uuid4().hex),
        auth_provider="google",
        google_sub=google_sub,
        primary_phone=primary_phone,
        timezone=timezone or "UTC",
        plan="starter",
        subscription_status="active",
    )

    try:
        db.add(new_tenant)
        db.commit()
        db.refresh(new_tenant)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account could not be created.",
        )

    return new_tenant


def _create_google_state_token(*, redirect_uri: str) -> str:
    expires = datetime.utcnow() + timedelta(minutes=10)
    # PKCE (works without client_secret)
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")
    payload = {
        "typ": "google_oauth_state",
        "redirect_uri": redirect_uri,
        "nonce": uuid.uuid4().hex,
        "pkce_verifier": code_verifier,
        "exp": expires,
    }
    return jwt.encode(payload, security.SECRET_KEY, algorithm=security.ALGORITHM)


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _verify_google_state_token(state: str) -> dict:
    try:
        payload = jwt.decode(state, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        if payload.get("typ") != "google_oauth_state":
            raise JWTError("Invalid state token type")
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state.",
        )


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
        auth_provider="local",
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


@router.get("/google/authorize", response_model=auth.GoogleAuthorizeResponse)
def google_authorize(redirect_uri: str):
    """Return a Google OAuth authorization URL for the frontend to redirect to."""
    client_id = _require_google_client_id()

    state = _create_google_state_token(redirect_uri=redirect_uri)
    state_payload = _verify_google_state_token(state)
    code_challenge = _pkce_challenge(state_payload["pkce_verifier"])
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": GOOGLE_SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    )

    return auth.GoogleAuthorizeResponse(
        authorization_url=f"{GOOGLE_AUTH_BASE_URL}?{query}",
        state=state,
    )


@router.post("/google/exchange", response_model=auth.TokenResponse)
def google_exchange(payload: auth.GoogleExchangeRequest, db: Session = Depends(get_db)):
    """Exchange a Google authorization code for an ID token, then login/signup a tenant."""
    client_id = _require_google_client_id()
    client_secret = settings.GOOGLE_CLIENT_SECRET or os.getenv("GOOGLE_CLIENT_SECRET")
    state_payload = _verify_google_state_token(payload.state)
    if state_payload.get("redirect_uri") != payload.redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="redirect_uri does not match OAuth state.",
        )

    code_verifier = state_payload.get("pkce_verifier")
    if not code_verifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state missing PKCE verifier.",
        )

    # Exchange authorization code for tokens
    try:
        token_data = {
            "client_id": client_id,
            "code": payload.code,
            "grant_type": "authorization_code",
            "redirect_uri": payload.redirect_uri,
            "code_verifier": code_verifier,
        }
        # If secret is configured (confidential client), include it.
        if client_secret:
            token_data["client_secret"] = client_secret

        token_resp = httpx.post(GOOGLE_TOKEN_URL, data=token_data, timeout=20.0)
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach Google token endpoint.",
        )

    if token_resp.status_code >= 400:
        err = None
        err_desc = None
        err_uri = None
        raw_body = None
        try:
            err_json = token_resp.json()
            err = err_json.get("error")
            err_desc = err_json.get("error_description")
            err_uri = err_json.get("error_uri")
        except Exception:
            raw_body = token_resp.text

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Google token exchange failed",
                "google_error": err,
                "google_error_description": err_desc,
                "google_error_uri": err_uri,
                "hint": (
                    "If google_error is invalid_client or unauthorized_client, you likely need GOOGLE_CLIENT_SECRET for a Web OAuth client. "
                    "If you cannot use a client secret, use /api/auth/google/credential (GIS) instead."
                ),
                "raw": raw_body,
            },
        )

    token_json = token_resp.json()
    id_tok = token_json.get("id_token")
    if not id_tok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google token response missing id_token.",
        )

    # Verify ID token
    try:
        claims = google_id_token.verify_oauth2_token(id_tok, GoogleAuthRequest(), client_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token.",
        )

    tenant = _login_or_signup_from_google_claims(
        db=db,
        claims=claims,
        business_name=payload.business_name,
        primary_phone=payload.primary_phone,
        timezone=payload.timezone,
    )

    # Create access token (same shape as local login)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={
            "tenant_id": str(tenant.id),
            "email": tenant.email,
            "plan": tenant.plan,
        },
        expires_delta=access_token_expires,
    )

    return auth.TokenResponse(
        access_token=access_token,
        token_type="bearer",
        tenant=auth.TenantResponse.from_orm(tenant),
    )


@router.post("/google/credential", response_model=auth.TokenResponse)
def google_credential(payload: auth.GoogleCredentialRequest, db: Session = Depends(get_db)):
    """Login/signup using a Google ID token (Google Identity Services).

    This flow requires only GOOGLE_CLIENT_ID (no client secret), because the frontend obtains
    an ID token (credential) directly from Google.
    """
    client_id = _require_google_client_id()

    try:
        claims = google_id_token.verify_oauth2_token(payload.credential, GoogleAuthRequest(), client_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential.",
        )

    tenant = _login_or_signup_from_google_claims(
        db=db,
        claims=claims,
        business_name=payload.business_name,
        primary_phone=payload.primary_phone,
        timezone=payload.timezone,
    )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={
            "tenant_id": str(tenant.id),
            "email": tenant.email,
            "plan": tenant.plan,
        },
        expires_delta=access_token_expires,
    )

    return auth.TokenResponse(
        access_token=access_token,
        token_type="bearer",
        tenant=auth.TenantResponse.from_orm(tenant),
    )