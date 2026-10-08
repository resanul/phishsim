from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.models.campaigns import Campaign
from app.models.content import EmailTemplate, LandingPage, SenderProfile
from app.models.enums import Permission
from app.models.recipients import RecipientGroup
from app.schemas.campaigns import CampaignCreate, ExclusionDefinition, TargetDefinition
from app.services import campaign_service
from app.services.analytics_service import campaign_risk_distribution
from app.web.deps import csrf_protect, require_web_permission
from app.web.render import render_page

router = APIRouter(prefix="/campaigns", tags=["web-campaigns"])


@router.get("")
def list_campaigns(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.CAMPAIGN_MANAGE))):
    campaigns = db.execute(select(Campaign).order_by(Campaign.created_at.desc())).scalars().all()
    return render_page(request, db, admin, "campaigns/list.html", campaigns=campaigns)


@router.get("/new")
def new_campaign_form(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.CAMPAIGN_CREATE))):
    templates_ = db.execute(select(EmailTemplate).where(EmailTemplate.is_active.is_(True))).scalars().all()
    landing_pages = db.execute(select(LandingPage).where(LandingPage.is_active.is_(True))).scalars().all()
    senders = db.execute(select(SenderProfile).where(SenderProfile.is_active.is_(True))).scalars().all()
    groups = db.execute(select(RecipientGroup)).scalars().all()
    return render_page(
        request, db, admin, "campaigns/new.html",
        templates_=templates_, landing_pages=landing_pages, senders=senders, groups=groups,
    )


@router.post("/new")
def create_campaign(
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(require_web_permission(Permission.CAMPAIGN_CREATE)),
    name: str = Form(...),
    description: str = Form(""),
    objective: str = Form(""),
    template_id: str = Form(...),
    landing_page_id: str = Form(...),
    sender_profile_id: str = Form(...),
    sending_rate_per_minute: int = Form(10),
    authorized_organization: str = Form(...),
    approved_domains: str = Form(""),
    campaign_purpose: str = Form(...),
    test_mode: str = Form(""),
    test_addresses: str = Form(""),
    departments: str = Form(""),
    group_ids: list[str] = Form(default_factory=list),
    _csrf=Depends(csrf_protect),
):
    data = CampaignCreate(
        name=name,
        description=description,
        objective=objective,
        template_id=template_id,
        landing_page_id=landing_page_id,
        sender_profile_id=sender_profile_id,
        sending_rate_per_minute=sending_rate_per_minute,
        authorized_organization=authorized_organization,
        approved_domains=[d.strip() for d in approved_domains.split(",") if d.strip()],
        campaign_purpose=campaign_purpose,
        test_mode=(test_mode == "on"),
        test_addresses=[a.strip() for a in test_addresses.split(",") if a.strip()],
        target_definition=TargetDefinition(
            departments=[d.strip() for d in departments.split(",") if d.strip()],
            group_ids=group_ids,
        ),
        exclusion_definition=ExclusionDefinition(exclude_test_accounts=False),
    )
    campaign = campaign_service.create_campaign(db, data, owner_admin_id=admin.id)
    return RedirectResponse(f"/campaigns/{campaign.id}?msg=Campaign+created.", status_code=303)


@router.get("/{campaign_id}")
def campaign_detail(campaign_id: str, request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.CAMPAIGN_MANAGE))):
    campaign = db.get(Campaign, campaign_id)
    confirmation = None
    if campaign.status in ("draft", "scheduled"):
        confirmation = campaign_service.build_confirmation(db, campaign)
    risk = campaign_risk_distribution(db, campaign)
    sent = [t for t in campaign.targets if t.sent_at is not None]
    clicked = [t for t in sent if t.clicked_at is not None]
    reported = [t for t in sent if t.reported_at is not None]
    return render_page(
        request, db, admin, "campaigns/detail.html",
        campaign=campaign, confirmation=confirmation, risk=risk,
        sent_count=len(sent), clicked_count=len(clicked), reported_count=len(reported),
    )


def _action(campaign_id: str, db: Session, admin, fn):
    campaign = db.get(Campaign, campaign_id)
    try:
        fn(db, campaign, admin.id)
        msg = "Action completed."
    except Exception as exc:  # noqa: BLE001
        return RedirectResponse(f"/campaigns/{campaign_id}?error={exc}", status_code=303)
    return RedirectResponse(f"/campaigns/{campaign_id}?msg={msg}", status_code=303)


@router.post("/{campaign_id}/start")
def start_campaign(campaign_id: str, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.CAMPAIGN_LAUNCH)), _csrf=Depends(csrf_protect)):
    return _action(campaign_id, db, admin, campaign_service.launch_campaign)


@router.post("/{campaign_id}/pause")
def pause_campaign(campaign_id: str, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.CAMPAIGN_MANAGE)), _csrf=Depends(csrf_protect)):
    return _action(campaign_id, db, admin, campaign_service.pause_campaign)


@router.post("/{campaign_id}/resume")
def resume_campaign(campaign_id: str, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.CAMPAIGN_MANAGE)), _csrf=Depends(csrf_protect)):
    return _action(campaign_id, db, admin, campaign_service.resume_campaign)


@router.post("/{campaign_id}/stop")
def stop_campaign(campaign_id: str, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.CAMPAIGN_MANAGE)), _csrf=Depends(csrf_protect)):
    return _action(campaign_id, db, admin, campaign_service.cancel_campaign)


@router.post("/{campaign_id}/kill-switch/engage")
def kill_switch_engage(
    campaign_id: str,
    db: Session = Depends(get_db),
    admin=Depends(require_web_permission(Permission.CAMPAIGN_MANAGE)),
    reason: str = Form("Engaged from dashboard"),
    _csrf=Depends(csrf_protect),
):
    campaign = db.get(Campaign, campaign_id)
    campaign_service.engage_kill_switch(db, campaign, admin.id, reason)
    return RedirectResponse(f"/campaigns/{campaign_id}?msg=Kill+switch+engaged.", status_code=303)


@router.post("/{campaign_id}/kill-switch/disengage")
def kill_switch_disengage(campaign_id: str, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.CAMPAIGN_MANAGE)), _csrf=Depends(csrf_protect)):
    campaign = db.get(Campaign, campaign_id)
    campaign_service.disengage_kill_switch(db, campaign, admin.id)
    return RedirectResponse(f"/campaigns/{campaign_id}?msg=Kill+switch+disengaged.", status_code=303)
