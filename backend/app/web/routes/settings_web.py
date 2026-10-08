from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.models.enums import Permission
from app.services import settings_service
from app.services.audit_service import log_action
from app.web.deps import csrf_protect, require_web_permission
from app.web.render import render_page

router = APIRouter(tags=["web-settings"])


@router.get("/settings")
def settings_page(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.SETTINGS_MANAGE))):
    org = settings_service.get_setting(db, "organization")
    privacy = settings_service.get_setting(db, "privacy")
    return render_page(request, db, admin, "settings/index.html", org=org, privacy=privacy)


@router.post("/settings/organization")
def update_organization(
    db: Session = Depends(get_db),
    admin=Depends(require_web_permission(Permission.SETTINGS_MANAGE)),
    name: str = Form(""),
    timezone: str = Form("UTC"),
    _csrf=Depends(csrf_protect),
):
    settings_service.set_setting(db, "organization", {"name": name, "timezone": timezone, "logo_url": ""})
    log_action(db, actor_id=admin.id, actor_email=admin.email, action="settings_changed", object_type="system_setting", object_id="organization")
    return RedirectResponse("/settings?msg=Organization+settings+saved.", status_code=303)


@router.post("/settings/privacy")
def update_privacy(
    db: Session = Depends(get_db),
    admin=Depends(require_web_permission(Permission.SETTINGS_MANAGE)),
    retention_days: int = Form(180),
    anonymize_after_days: int = Form(90),
    auto_delete_events: str = Form(""),
    _csrf=Depends(csrf_protect),
):
    settings_service.set_setting(
        db, "privacy",
        {"retention_days": retention_days, "anonymize_after_days": anonymize_after_days, "auto_delete_events": auto_delete_events == "on"},
    )
    log_action(db, actor_id=admin.id, actor_email=admin.email, action="settings_changed", object_type="system_setting", object_id="privacy")
    return RedirectResponse("/settings?msg=Privacy+settings+saved.", status_code=303)


@router.post("/emergency/stop")
def emergency_stop_web(
    db: Session = Depends(get_db),
    admin=Depends(require_web_permission(Permission.CAMPAIGN_MANAGE)),
    reason: str = Form("Engaged from dashboard"),
    _csrf=Depends(csrf_protect),
):
    from sqlalchemy import select

    from app.models.campaigns import Campaign
    from app.models.enums import CampaignStatus

    settings_service.engage_global_stop(db, reason)
    running = db.execute(select(Campaign).where(Campaign.status == CampaignStatus.RUNNING.value)).scalars().all()
    for c in running:
        c.status = CampaignStatus.PAUSED.value
        db.add(c)
    db.commit()
    log_action(db, actor_id=admin.id, actor_email=admin.email, action="global_emergency_stop_engaged", metadata={"reason": reason, "via": "web"})
    return RedirectResponse("/?msg=Emergency+stop+engaged.+All+running+campaigns+paused.", status_code=303)


@router.post("/emergency/resume")
def emergency_resume_web(db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.CAMPAIGN_MANAGE)), _csrf=Depends(csrf_protect)):
    settings_service.disengage_global_stop(db)
    log_action(db, actor_id=admin.id, actor_email=admin.email, action="global_emergency_stop_disengaged", metadata={"via": "web"})
    return RedirectResponse("/?msg=Emergency+stop+disengaged.", status_code=303)
