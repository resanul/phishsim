from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.campaigns import Campaign
from app.models.enums import Permission
from app.models.identity import Administrator
from app.schemas.campaigns import CampaignConfirmation, CampaignCreate, CampaignOut, KillSwitchRequest
from app.services import campaign_service
from app.services.analytics_service import campaign_risk_distribution

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


def _get_campaign_or_404(db: Session, campaign_id: str) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    return campaign


@router.get("", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db), _=Depends(require_permission(Permission.CAMPAIGN_MANAGE))):
    return db.execute(select(Campaign)).scalars().all()


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: CampaignCreate,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.CAMPAIGN_CREATE)),
):
    return campaign_service.create_campaign(db, payload, owner_admin_id=actor.id)


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: str, db: Session = Depends(get_db), _=Depends(require_permission(Permission.CAMPAIGN_MANAGE))):
    return _get_campaign_or_404(db, campaign_id)


@router.get("/{campaign_id}/confirmation", response_model=CampaignConfirmation)
def get_confirmation(campaign_id: str, db: Session = Depends(get_db), _=Depends(require_permission(Permission.CAMPAIGN_LAUNCH))):
    campaign = _get_campaign_or_404(db, campaign_id)
    return campaign_service.build_confirmation(db, campaign)


@router.post("/{campaign_id}/start", response_model=CampaignOut)
def start_campaign(campaign_id: str, db: Session = Depends(get_db), actor: Administrator = Depends(require_permission(Permission.CAMPAIGN_LAUNCH))):
    campaign = _get_campaign_or_404(db, campaign_id)
    return campaign_service.launch_campaign(db, campaign, actor.id)


@router.post("/{campaign_id}/pause", response_model=CampaignOut)
def pause_campaign(campaign_id: str, db: Session = Depends(get_db), actor: Administrator = Depends(require_permission(Permission.CAMPAIGN_MANAGE))):
    campaign = _get_campaign_or_404(db, campaign_id)
    return campaign_service.pause_campaign(db, campaign, actor.id)


@router.post("/{campaign_id}/resume", response_model=CampaignOut)
def resume_campaign(campaign_id: str, db: Session = Depends(get_db), actor: Administrator = Depends(require_permission(Permission.CAMPAIGN_MANAGE))):
    campaign = _get_campaign_or_404(db, campaign_id)
    return campaign_service.resume_campaign(db, campaign, actor.id)


@router.post("/{campaign_id}/stop", response_model=CampaignOut)
def stop_campaign(campaign_id: str, db: Session = Depends(get_db), actor: Administrator = Depends(require_permission(Permission.CAMPAIGN_MANAGE))):
    campaign = _get_campaign_or_404(db, campaign_id)
    return campaign_service.cancel_campaign(db, campaign, actor.id)


@router.post("/{campaign_id}/kill-switch/engage", response_model=CampaignOut)
def engage_kill_switch(campaign_id: str, payload: KillSwitchRequest, db: Session = Depends(get_db), actor: Administrator = Depends(require_permission(Permission.CAMPAIGN_MANAGE))):
    campaign = _get_campaign_or_404(db, campaign_id)
    return campaign_service.engage_kill_switch(db, campaign, actor.id, payload.reason)


@router.post("/{campaign_id}/kill-switch/disengage", response_model=CampaignOut)
def disengage_kill_switch(campaign_id: str, db: Session = Depends(get_db), actor: Administrator = Depends(require_permission(Permission.CAMPAIGN_MANAGE))):
    campaign = _get_campaign_or_404(db, campaign_id)
    return campaign_service.disengage_kill_switch(db, campaign, actor.id)


@router.get("/{campaign_id}/analytics")
def campaign_analytics(campaign_id: str, db: Session = Depends(get_db), _=Depends(require_permission(Permission.ANALYTICS_VIEW))):
    campaign = _get_campaign_or_404(db, campaign_id)
    sent = [t for t in campaign.targets if t.sent_at is not None]
    clicked = [t for t in sent if t.clicked_at is not None]
    reported = [t for t in sent if t.reported_at is not None]
    return {
        "campaign_id": campaign.id,
        "status": campaign.status,
        "total_targets": len(campaign.targets),
        "sent": len(sent),
        "clicked": len(clicked),
        "reported": len(reported),
        "risk_distribution": campaign_risk_distribution(db, campaign),
    }
