from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_admin
from app.database import get_db
from app.models.identity import Administrator
from app.schemas.auth import LoginRequest, LoginResponse, MFASetupResponse, MFAVerifyRequest
from app.security.mfa import encrypt_totp_secret, generate_totp_secret, get_provisioning_uri, verify_totp
from app.security.passwords import verify_password
from app.security.rate_limit import is_rate_limited
from app.services import auth_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    ip = get_client_ip(request)
    if is_rate_limited(f"login:{ip}", max_requests=10, window_seconds=60):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts. Try again later.")

    admin, mfa_required, error = auth_service.authenticate(db, payload.email, payload.password, payload.totp_code, source_ip=ip)
    if admin is None:
        if mfa_required:
            return LoginResponse(access_token="", mfa_required=True)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error or "Invalid credentials.")

    token = auth_service.issue_token(admin)
    return LoginResponse(access_token=token)


@router.post("/mfa/setup", response_model=MFASetupResponse)
def setup_mfa(admin: Administrator = Depends(get_current_admin), db: Session = Depends(get_db)) -> MFASetupResponse:
    secret = generate_totp_secret()
    admin.mfa_secret_encrypted = encrypt_totp_secret(secret)
    admin.mfa_enabled = False  # not enabled until verified
    db.add(admin)
    db.commit()
    uri = get_provisioning_uri(secret, admin.email)
    return MFASetupResponse(secret=secret, provisioning_uri=uri)


@router.post("/mfa/verify")
def verify_mfa_enable(payload: MFAVerifyRequest, admin: Administrator = Depends(get_current_admin), db: Session = Depends(get_db)) -> dict:
    if not verify_totp(admin.mfa_secret_encrypted or "", payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code.")
    admin.mfa_enabled = True
    db.add(admin)
    db.commit()
    log_action(db, actor_id=admin.id, actor_email=admin.email, action="mfa_enabled", object_type="administrator", object_id=admin.id)
    return {"mfa_enabled": True}


@router.get("/me")
def me(admin: Administrator = Depends(get_current_admin)) -> dict:
    return {
        "id": admin.id,
        "email": admin.email,
        "full_name": admin.full_name,
        "role": admin.role.name,
        "mfa_enabled": admin.mfa_enabled,
        "is_super_admin": admin.is_super_admin,
    }
