from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.campaigns import Campaign
from app.models.enums import CampaignStatus, Permission
from app.models.identity import Administrator
from app.services import settings_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/emergency", tags=["emergency"])


@router.post("/stop")
def emergency_stop(
    reason: str,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.CAMPAIGN_MANAGE)),
):
    settings_service.engage_global_stop(db, reason)
    running = db.execute(select(Campaign).where(Campaign.status == CampaignStatus.RUNNING.value)).scalars().all()
    for c in running:
        c.status = CampaignStatus.PAUSED.value
        db.add(c)
    db.commit()
    log_action(db, actor_id=actor.id, actor_email=actor.email, action="global_emergency_stop_engaged", metadata={"reason": reason, "paused_campaigns": [c.id for c in running]})
    return {"engaged": True, "paused_campaigns": [c.id for c in running]}


@router.post("/resume")
def emergency_resume(
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.CAMPAIGN_MANAGE)),
):
    settings_service.disengage_global_stop(db)
    log_action(db, actor_id=actor.id, actor_email=actor.email, action="global_emergency_stop_disengaged")
    return {"engaged": False}


@router.get("/status")
def emergency_status(db: Session = Depends(get_db), _=Depends(require_permission(Permission.CAMPAIGN_MANAGE))):
    return settings_service.get_setting(db, settings_service.GLOBAL_EMERGENCY_STOP_KEY)
