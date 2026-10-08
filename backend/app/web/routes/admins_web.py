from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.models.enums import Permission
from app.models.identity import Administrator
from app.security.passwords import hash_password, validate_password_policy
from app.services.audit_service import log_action
from app.services.auth_service import get_admin_by_email, get_or_create_role
from app.web.deps import csrf_protect, require_web_permission
from app.web.render import render_page

router = APIRouter(prefix="/administration", tags=["web-admins"])


@router.get("")
def list_admins(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.USER_MANAGE))):
    rows = db.execute(select(Administrator)).scalars().all()
    return render_page(request, db, admin, "admins/list.html", items=rows)


@router.post("/add")
def add_admin(
    request: Request,
    db: Session = Depends(get_db),
    actor=Depends(require_web_permission(Permission.USER_MANAGE)),
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role_name: str = Form("read_only"),
    _csrf=Depends(csrf_protect),
):
    if get_admin_by_email(db, email) is not None:
        return RedirectResponse("/administration?error=An+administrator+with+this+email+already+exists.", status_code=303)

    problems = validate_password_policy(password)
    if problems:
        return RedirectResponse(f"/administration?error={'; '.join(problems)}", status_code=303)

    role = get_or_create_role(db, role_name)
    new_admin = Administrator(email=email.lower(), full_name=full_name, hashed_password=hash_password(password), role_id=role.id, is_super_admin=(role_name == "super_admin"))
    db.add(new_admin)
    db.commit()
    log_action(db, actor_id=actor.id, actor_email=actor.email, action="administrator_created", object_type="administrator", object_id=new_admin.id, metadata={"role": role_name, "via": "web"})
    return RedirectResponse("/administration?msg=Administrator+created.", status_code=303)


@router.post("/{admin_id}/deactivate")
def deactivate_admin(admin_id: str, db: Session = Depends(get_db), actor=Depends(require_web_permission(Permission.USER_MANAGE)), _csrf=Depends(csrf_protect)):
    target = db.get(Administrator, admin_id)
    if target is not None:
        target.is_active = False
        db.add(target)
        db.commit()
        log_action(db, actor_id=actor.id, actor_email=actor.email, action="administrator_deactivated", object_type="administrator", object_id=target.id, metadata={"via": "web"})
    return RedirectResponse("/administration?msg=Administrator+deactivated.", status_code=303)
