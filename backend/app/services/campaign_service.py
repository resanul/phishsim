from __future__ import annotations

import datetime as dt

from fastapi import HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models.campaigns import Campaign, CampaignTarget
from app.models.recipients import Recipient
from app.models.enums import CampaignStatus
from app.schemas.campaigns import CampaignCreate, CampaignConfirmation
from app.security.tokens import generate_tracking_token
from app.services.audit_service import log_action


def _matches_target_definition(recipient: Recipient, target_def: dict) -> bool:
    if not any(target_def.get(k) for k in ("recipient_ids", "group_ids", "departments", "locations", "job_titles", "tags")):
        return True  # empty target definition == everyone (still subject to exclusions below)

    if recipient.id in (target_def.get("recipient_ids") or []):
        return True
    group_ids = set(target_def.get("group_ids") or [])
    if group_ids and any(g.id in group_ids for g in recipient.groups):
        return True
    if recipient.department and recipient.department in (target_def.get("departments") or []):
        return True
    if recipient.location and recipient.location in (target_def.get("locations") or []):
        return True
    if recipient.job_title and recipient.job_title in (target_def.get("job_titles") or []):
        return True
    tags = set(target_def.get("tags") or [])
    if tags and tags.intersection(recipient.tags or []):
        return True
    return False


def _is_excluded(recipient: Recipient, exclusion_def: dict) -> bool:
    if recipient.id in (exclusion_def.get("recipient_ids") or []):
        return True
    if recipient.domain in {d.lower() for d in (exclusion_def.get("domains") or [])}:
        return True
    if exclusion_def.get("exclude_test_accounts") and recipient.is_test_address:
        return True
    if recipient.is_excluded:
        return True
    if not recipient.is_active:
        return True
    return False


def resolve_targets(db: Session, campaign: Campaign) -> list[Recipient]:
    """Resolve the recipients a campaign would send to, honoring target
    definition, exclusions, the approved-domain allowlist, and test mode.
    This is intentionally pure/side-effect-free so it can back both the
    pre-launch confirmation screen and the actual send fan-out."""
    all_recipients = db.execute(select(Recipient)).scalars().all()

    if campaign.test_mode:
        addresses = {a.lower() for a in (campaign.test_addresses or [])}
        return [r for r in all_recipients if r.email.lower() in addresses]

    matched = [
        r
        for r in all_recipients
        if _matches_target_definition(r, campaign.target_definition or {})
        and not _is_excluded(r, campaign.exclusion_definition or {})
    ]

    approved = {d.lower() for d in (campaign.approved_domains or [])}
    if approved:
        matched = [r for r in matched if r.domain in approved]

    return matched


def build_confirmation(db: Session, campaign: Campaign) -> CampaignConfirmation:
    targets = resolve_targets(db, campaign)
    all_recipients = db.execute(select(Recipient)).scalars().all()
    considered = len(all_recipients) if not campaign.test_mode else len(campaign.test_addresses or [])
    excluded_count = max(considered - len(targets), 0)

    duration_minutes = 0.0
    if campaign.sending_rate_per_minute > 0:
        duration_minutes = len(targets) / campaign.sending_rate_per_minute

    return CampaignConfirmation(
        campaign_id=campaign.id,
        recipient_count=len(targets),
        template_name=campaign.template.name if campaign.template else "",
        landing_page_name=campaign.landing_page.name if campaign.landing_page else "",
        start_at=campaign.start_at,
        end_at=campaign.end_at,
        sending_rate_per_minute=campaign.sending_rate_per_minute,
        estimated_duration_minutes=round(duration_minutes, 1),
        test_mode=campaign.test_mode,
        excluded_count=excluded_count,
    )


def create_campaign(db: Session, data: CampaignCreate, owner_admin_id: str) -> Campaign:
    campaign = Campaign(
        name=data.name,
        description=data.description,
        objective=data.objective,
        campaign_type=data.campaign_type,
        template_id=data.template_id,
        landing_page_id=data.landing_page_id,
        sender_profile_id=data.sender_profile_id,
        status=CampaignStatus.DRAFT.value,
        start_at=data.start_at,
        end_at=data.end_at,
        timezone=data.timezone,
        sending_rate_per_minute=data.sending_rate_per_minute,
        randomize_delivery_window_minutes=data.randomize_delivery_window_minutes,
        target_definition=data.target_definition.model_dump(),
        exclusion_definition=data.exclusion_definition.model_dump(),
        owner_admin_id=owner_admin_id,
        authorized_organization=data.authorized_organization,
        approved_domains=[d.lower() for d in data.approved_domains],
        campaign_purpose=data.campaign_purpose,
        test_mode=data.test_mode,
        test_addresses=[a.lower() for a in data.test_addresses],
        retention_days=data.retention_days,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    log_action(db, actor_id=owner_admin_id, action="campaign_created", object_type="campaign", object_id=campaign.id)
    return campaign


def _require_status(campaign: Campaign, allowed: set[str]) -> None:
    if campaign.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Campaign is '{campaign.status}'; this action requires one of: {', '.join(sorted(allowed))}",
        )


def launch_campaign(db: Session, campaign: Campaign, actor_id: str) -> Campaign:
    _require_status(campaign, {CampaignStatus.DRAFT.value, CampaignStatus.SCHEDULED.value})
    if campaign.kill_switch_engaged:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign kill switch is engaged.")

    targets = resolve_targets(db, campaign)
    if not targets:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No recipients resolved for this campaign; nothing to launch.")

    existing_recipient_ids = {t.recipient_id for t in campaign.targets}
    now = dt.datetime.now(dt.timezone.utc)
    for recipient in targets:
        if recipient.id in existing_recipient_ids:
            continue
        db.add(
            CampaignTarget(
                campaign_id=campaign.id,
                recipient_id=recipient.id,
                tracking_token=generate_tracking_token(),
                scheduled_send_at=now,
            )
        )

    campaign.status = CampaignStatus.RUNNING.value if not campaign.start_at or campaign.start_at <= now else CampaignStatus.SCHEDULED.value
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    log_action(db, actor_id=actor_id, action="campaign_launched", object_type="campaign", object_id=campaign.id, metadata={"recipient_count": len(targets)})
    return campaign


def pause_campaign(db: Session, campaign: Campaign, actor_id: str) -> Campaign:
    _require_status(campaign, {CampaignStatus.RUNNING.value, CampaignStatus.SCHEDULED.value})
    campaign.status = CampaignStatus.PAUSED.value
    db.add(campaign)
    db.commit()
    log_action(db, actor_id=actor_id, action="campaign_paused", object_type="campaign", object_id=campaign.id)
    return campaign


def resume_campaign(db: Session, campaign: Campaign, actor_id: str) -> Campaign:
    _require_status(campaign, {CampaignStatus.PAUSED.value})
    if campaign.kill_switch_engaged:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign kill switch is engaged; clear it before resuming.")
    campaign.status = CampaignStatus.RUNNING.value
    db.add(campaign)
    db.commit()
    log_action(db, actor_id=actor_id, action="campaign_resumed", object_type="campaign", object_id=campaign.id)
    return campaign


def cancel_campaign(db: Session, campaign: Campaign, actor_id: str) -> Campaign:
    _require_status(
        campaign,
        {CampaignStatus.DRAFT.value, CampaignStatus.SCHEDULED.value, CampaignStatus.RUNNING.value, CampaignStatus.PAUSED.value},
    )
    campaign.status = CampaignStatus.CANCELLED.value
    db.add(campaign)
    db.commit()
    log_action(db, actor_id=actor_id, action="campaign_cancelled", object_type="campaign", object_id=campaign.id)
    return campaign


def engage_kill_switch(db: Session, campaign: Campaign, actor_id: str, reason: str) -> Campaign:
    campaign.kill_switch_engaged = True
    campaign.kill_switch_engaged_at = dt.datetime.now(dt.timezone.utc)
    campaign.kill_switch_reason = reason
    if campaign.status == CampaignStatus.RUNNING.value:
        campaign.status = CampaignStatus.PAUSED.value
    db.add(campaign)
    db.commit()
    log_action(db, actor_id=actor_id, action="campaign_kill_switch_engaged", object_type="campaign", object_id=campaign.id, metadata={"reason": reason})
    return campaign


def disengage_kill_switch(db: Session, campaign: Campaign, actor_id: str) -> Campaign:
    campaign.kill_switch_engaged = False
    campaign.kill_switch_reason = ""
    db.add(campaign)
    db.commit()
    log_action(db, actor_id=actor_id, action="campaign_kill_switch_disengaged", object_type="campaign", object_id=campaign.id)
    return campaign
