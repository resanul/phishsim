from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_permission
from app.database import get_db
from app.models.enums import Permission
from app.models.identity import Administrator
from app.schemas.auth import AdminCreate, AdminOut
from app.security.passwords import hash_password, validate_password_policy
from app.services.audit_service import log_action
from app.services.auth_service import get_admin_by_email, get_or_create_role

router = APIRouter(prefix="/api/admins", tags=["administrators"])


@router.get("", response_model=list[AdminOut])
def list_admins(db: Session = Depends(get_db), _=Depends(require_permission(Permission.USER_MANAGE))):
    admins = db.execute(select(Administrator)).scalars().all()
    return [AdminOut(id=a.id, email=a.email, full_name=a.full_name, role_name=a.role.name, is_active=a.is_active, mfa_enabled=a.mfa_enabled) for a in admins]


@router.post("", response_model=AdminOut, status_code=status.HTTP_201_CREATED)
def create_admin(
    payload: AdminCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.USER_MANAGE)),
):
    if get_admin_by_email(db, payload.email) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An administrator with this email already exists.")

    problems = validate_password_policy(payload.password)
    if problems:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(problems))

    role = get_or_create_role(db, payload.role_name)
    admin = Administrator(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role_id=role.id,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    log_action(
        db,
        actor_id=actor.id,
        actor_email=actor.email,
        action="administrator_created",
        object_type="administrator",
        object_id=admin.id,
        source_ip=get_client_ip(request),
        metadata={"role": role.name},
    )
    return AdminOut(id=admin.id, email=admin.email, full_name=admin.full_name, role_name=role.name, is_active=admin.is_active, mfa_enabled=admin.mfa_enabled)


@router.post("/{admin_id}/deactivate")
def deactivate_admin(
    admin_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.USER_MANAGE)),
):
    target = db.get(Administrator, admin_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Administrator not found.")
    target.is_active = False
    db.add(target)
    db.commit()
    log_action(db, actor_id=actor.id, actor_email=actor.email, action="administrator_deactivated", object_type="administrator", object_id=target.id, source_ip=get_client_ip(request))
    return {"deactivated": True}
