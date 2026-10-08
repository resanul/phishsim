from __future__ import annotations

import datetime as dt

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.identity import Administrator, Role
from app.security.mfa import verify_totp
from app.security.passwords import verify_password
from app.security.tokens import create_access_token
from app.services.audit_service import log_action


class AuthError(Exception):
    pass


def get_admin_by_email(db: Session, email: str) -> Administrator | None:
    return db.execute(select(Administrator).where(Administrator.email == email.lower())).scalar_one_or_none()


def authenticate(db: Session, email: str, password: str, totp_code: str | None, source_ip: str = "") -> tuple[Administrator | None, bool, str]:
    """Returns (administrator_or_None, mfa_required, error_message)."""
    admin = get_admin_by_email(db, email)
    if admin is None:
        log_action(db, action="login_failed", object_type="administrator", object_id=email, source_ip=source_ip, result="failure", metadata={"reason": "no_such_account"})
        return None, False, "Invalid email or password."

    now = dt.datetime.now(dt.timezone.utc)
    if admin.locked_until and admin.locked_until > now:
        log_action(db, actor_id=admin.id, actor_email=admin.email, action="login_failed", object_type="administrator", object_id=admin.id, source_ip=source_ip, result="failure", metadata={"reason": "locked"})
        return None, False, "Account is temporarily locked due to repeated failed logins."

    if not admin.is_active:
        log_action(db, actor_id=admin.id, actor_email=admin.email, action="login_failed", object_type="administrator", object_id=admin.id, source_ip=source_ip, result="failure", metadata={"reason": "inactive"})
        return None, False, "Account is disabled."

    if not verify_password(password, admin.hashed_password):
        admin.failed_login_count += 1
        if admin.failed_login_count >= settings.max_failed_logins:
            admin.locked_until = now + dt.timedelta(minutes=settings.lockout_minutes)
        db.add(admin)
        db.commit()
        log_action(db, actor_id=admin.id, actor_email=admin.email, action="login_failed", object_type="administrator", object_id=admin.id, source_ip=source_ip, result="failure", metadata={"reason": "bad_password"})
        return None, False, "Invalid email or password."

    if settings.require_mfa_for_admins and admin.mfa_enabled:
        if not totp_code:
            return None, True, "MFA code required."
        if not verify_totp(admin.mfa_secret_encrypted or "", totp_code):
            admin.failed_login_count += 1
            db.add(admin)
            db.commit()
            log_action(db, actor_id=admin.id, actor_email=admin.email, action="login_failed", object_type="administrator", object_id=admin.id, source_ip=source_ip, result="failure", metadata={"reason": "bad_mfa"})
            return None, True, "Invalid MFA code."

    admin.failed_login_count = 0
    admin.locked_until = None
    admin.last_login_at = now
    db.add(admin)
    db.commit()
    log_action(db, actor_id=admin.id, actor_email=admin.email, action="login_success", object_type="administrator", object_id=admin.id, source_ip=source_ip, result="success")
    return admin, False, ""


def issue_token(admin: Administrator) -> str:
    return create_access_token(subject=admin.id, extra_claims={"role": admin.role.name, "email": admin.email})


def get_or_create_role(db: Session, role_name: str) -> Role:
    role = db.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown role: {role_name}")
    return role
