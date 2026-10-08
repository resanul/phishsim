from __future__ import annotations

import datetime as dt
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.campaigns import Campaign, CampaignEvent, CampaignTarget, TrainingSession
from app.models.enums import CampaignEventType


def hash_ip(ip: str) -> str:
    if not ip:
        return ""
    return hashlib.sha256((settings.secret_key + "|" + ip).encode("utf-8")).hexdigest()


def get_target_by_token(db: Session, campaign_id: str, token: str) -> CampaignTarget | None:
    return db.execute(
        select(CampaignTarget).where(
            CampaignTarget.campaign_id == campaign_id,
            CampaignTarget.tracking_token == token,
        )
    ).scalar_one_or_none()


def record_event(
    db: Session,
    target: CampaignTarget,
    event_type: CampaignEventType,
    *,
    ip: str = "",
    user_agent: str = "",
    metadata: dict | None = None,
) -> CampaignEvent:
    now = dt.datetime.now(dt.timezone.utc)
    event = CampaignEvent(
        campaign_id=target.campaign_id,
        target_id=target.id,
        event_type=event_type.value,
        occurred_at=now,
        ip_hash=hash_ip(ip),
        user_agent=(user_agent or "")[:500],
        metadata_json=metadata or {},
    )
    db.add(event)

    if event_type == CampaignEventType.LINK_CLICKED and target.clicked_at is None:
        target.clicked_at = now
    if event_type == CampaignEventType.REPORTED_PHISHING and target.reported_at is None:
        target.reported_at = now
    if event_type == CampaignEventType.TRAINING_VIEWED and target.training_completed_at is None:
        target.training_completed_at = now
    if event_type == CampaignEventType.SIMULATION_COMPLETED and target.completed_at is None:
        target.completed_at = now
    if event_type in (CampaignEventType.LINK_CLICKED, CampaignEventType.LANDING_VISITED, CampaignEventType.FORM_INTERACTED):
        target.interaction_count += 1

    db.add(target)
    db.commit()
    db.refresh(event)
    return event


def handle_synthetic_form_submission(db: Session, target: CampaignTarget, *, ip: str, user_agent: str) -> None:
    """Record that the demo form was interacted with WITHOUT ever persisting
    submitted field values. This function intentionally never receives or
    touches the submitted form payload -- callers must not pass it in."""
    record_event(
        db,
        target,
        CampaignEventType.FORM_INTERACTED,
        ip=ip,
        user_agent=user_agent,
        metadata={"note": "synthetic demo form; no submitted values were stored"},
    )


def start_training_session(db: Session, target: CampaignTarget, module_key: str = "red_flags_overview") -> TrainingSession:
    session = TrainingSession(target_id=target.id, started_at=dt.datetime.now(dt.timezone.utc), module_key=module_key)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def complete_training_session(db: Session, session: TrainingSession, score: int | None = None) -> TrainingSession:
    session.completed_at = dt.datetime.now(dt.timezone.utc)
    session.score = score
    db.add(session)
    db.commit()
    db.refresh(session)
    return session
