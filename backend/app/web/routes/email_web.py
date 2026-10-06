from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.models.content import SenderProfile
from app.models.enums import Permission
from app.security.crypto import encrypt_secret
from app.services.audit_service import log_action
from app.web.deps import csrf_protect, require_web_permission
from app.web.render import render_page

router = APIRouter(prefix="/settings/email", tags=["web-email"])

@router.get("")
def email_settings(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.SETTINGS_MANAGE))):
    profiles = db.execute(select(SenderProfile).order_by(SenderProfile.created_at.desc())).scalars().all()
    return render_page(request, db, admin, "settings/email.html", profiles=profiles)

@router.post("/add")
def add_sender_profile(
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(require_web_permission(Permission.SETTINGS_MANAGE)),
    name: str = Form(...),
    from_name: str = Form(...),
    from_email: str = Form(...),
    reply_to: str = Form(""),
    smtp_host: str = Form(...),
    smtp_port: int = Form(587),
    smtp_use_tls: str = Form("on"),
    smtp_username: str = Form(""),
    smtp_password: str = Form(""),
    _csrf=Depends(csrf_protect),
):
    profile = SenderProfile(
        name=name.strip(), from_name=from_name.strip(), from_email=from_email.strip(),
        reply_to=reply_to.strip(), smtp_host=smtp_host.strip(), smtp_port=smtp_port,
        smtp_use_tls=(smtp_use_tls == "on"), smtp_username=smtp_username.strip(),
        smtp_password_encrypted=encrypt_secret(smtp_password) if smtp_password else "",
        is_active=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    log_action(db, actor_id=admin.id, actor_email=admin.email, action="sender_profile_created",
               object_type="sender_profile", object_id=profile.id, metadata={"via": "web"})
    return RedirectResponse("/settings/email?msg=SMTP+sender+profile+created.", status_code=303)

@router.post("/{profile_id}/toggle")
def toggle_sender_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    admin=Depends(require_web_permission(Permission.SETTINGS_MANAGE)),
    _csrf=Depends(csrf_protect),
):
    profile = db.get(SenderProfile, profile_id)
    if profile is None:
        return RedirectResponse("/settings/email?error=Sender+profile+not+found.", status_code=303)
    profile.is_active = not profile.is_active
    db.add(profile)
    db.commit()
    log_action(db, actor_id=admin.id, actor_email=admin.email, action="sender_profile_toggled",
               object_type="sender_profile", object_id=profile.id,
               metadata={"active": profile.is_active, "via": "web"})
    state = "activated" if profile.is_active else "deactivated"
    return RedirectResponse(f"/settings/email?msg=Sender+profile+{state}.", status_code=303)
