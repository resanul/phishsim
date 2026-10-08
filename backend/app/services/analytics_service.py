from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.campaigns import Campaign, CampaignTarget
from app.models.enums import CampaignStatus
from app.services.risk_service import score_target


def dashboard_kpis(db: Session) -> dict:
    campaigns = db.execute(select(Campaign)).scalars().all()
    all_targets: list[CampaignTarget] = [t for c in campaigns for t in c.targets]

    total_campaigns = len(campaigns)
    active_campaigns = sum(1 for c in campaigns if c.status == CampaignStatus.RUNNING.value)
    completed_campaigns = sum(1 for c in campaigns if c.status == CampaignStatus.COMPLETED.value)

    sent = [t for t in all_targets if t.sent_at is not None]
    clicked = [t for t in sent if t.clicked_at is not None]
    reported = [t for t in sent if t.reported_at is not None]
    completed = [t for t in sent if t.completed_at is not None]

    def pct(n: int, d: int) -> float:
        return round(100 * n / d, 1) if d else 0.0

    report_times = [
        (t.reported_at - t.sent_at).total_seconds() / 60.0
        for t in reported
        if t.sent_at and t.reported_at
    ]
    avg_time_to_report = round(sum(report_times) / len(report_times), 1) if report_times else None

    return {
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "completed_campaigns": completed_campaigns,
        "emails_sent": len(sent),
        "delivery_rate_pct": pct(len(sent), sum(len(c.targets) for c in campaigns)),
        "click_rate_pct": pct(len(clicked), len(sent)),
        "report_rate_pct": pct(len(reported), len(sent)),
        "simulation_completion_rate_pct": pct(len(completed), len(sent)),
        "avg_time_to_report_minutes": avg_time_to_report,
    }


def employee_metrics(db: Session) -> dict:
    campaigns = db.execute(select(Campaign)).scalars().all()
    all_targets: list[CampaignTarget] = [t for c in campaigns for t in c.targets]
    participants = {t.recipient_id for t in all_targets}
    clicked = {t.recipient_id for t in all_targets if t.clicked_at is not None}
    reported = {t.recipient_id for t in all_targets if t.reported_at is not None}
    trained = {t.recipient_id for t in all_targets if t.training_completed_at is not None}

    repeat = defaultdict(int)
    for t in all_targets:
        if t.clicked_at is not None:
            repeat[t.recipient_id] += 1
    repeat_offenders = sum(1 for v in repeat.values() if v > 1)

    return {
        "total_participants": len(participants),
        "clicked": len(clicked),
        "reported": len(reported),
        "completed_training": len(trained),
        "repeat_interactions": repeat_offenders,
    }


def department_metrics(db: Session) -> list[dict]:
    campaigns = db.execute(select(Campaign)).scalars().all()
    all_targets: list[CampaignTarget] = [t for c in campaigns for t in c.targets]

    by_dept: dict[str, list[CampaignTarget]] = defaultdict(list)
    for t in all_targets:
        dept = t.recipient.department or "Unassigned"
        by_dept[dept].append(t)

    rows = []
    for dept, targets in by_dept.items():
        sent = [t for t in targets if t.sent_at is not None]
        clicked = [t for t in sent if t.clicked_at is not None]
        reported = [t for t in sent if t.reported_at is not None]
        rows.append(
            {
                "department": dept,
                "sent": len(sent),
                "click_rate_pct": round(100 * len(clicked) / len(sent), 1) if sent else 0.0,
                "report_rate_pct": round(100 * len(reported) / len(sent), 1) if sent else 0.0,
            }
        )
    return sorted(rows, key=lambda r: r["department"])


def campaign_risk_distribution(db: Session, campaign: Campaign) -> dict:
    counts = defaultdict(int)
    for target in campaign.targets:
        if target.sent_at is None:
            continue
        result = score_target(target)
        counts[result.level] += 1
    return dict(counts)
