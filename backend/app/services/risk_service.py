from __future__ import annotations

from dataclasses import dataclass

from app.models.campaigns import CampaignTarget
from app.models.enums import RiskLevel

DEFAULT_WEIGHTS = {
    "clicked": 40.0,
    "repeat_interaction": 15.0,  # per extra interaction beyond the first
    "reported": -30.0,
    "training_completed": -20.0,
}

DEFAULT_THRESHOLDS = {
    "low": 20,
    "medium": 50,
    "high": 80,
}


@dataclass
class RiskResult:
    score: float
    level: str


def score_target(target: CampaignTarget, weights: dict | None = None, thresholds: dict | None = None) -> RiskResult:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    score = 0.0
    if target.clicked_at is not None:
        score += w["clicked"]
    if target.interaction_count > 1:
        score += w["repeat_interaction"] * (target.interaction_count - 1)
    if target.reported_at is not None:
        score += w["reported"]
    if target.training_completed_at is not None:
        score += w["training_completed"]

    score = max(0.0, score)

    if target.clicked_at is not None and target.training_completed_at is None:
        level = RiskLevel.NEEDS_TRAINING.value
    elif score >= t["high"]:
        level = RiskLevel.HIGH.value
    elif score >= t["medium"]:
        level = RiskLevel.MEDIUM.value
    else:
        level = RiskLevel.LOW.value

    return RiskResult(score=round(score, 1), level=level)
