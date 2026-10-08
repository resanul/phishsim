from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.models.audit import SystemSetting

GLOBAL_EMERGENCY_STOP_KEY = "global_emergency_stop"

DEFAULTS: dict[str, dict] = {
    GLOBAL_EMERGENCY_STOP_KEY: {"engaged": False, "reason": "", "engaged_at": None},
    "privacy": {"retention_days": 180, "anonymize_after_days": 90, "auto_delete_events": False},
    "organization": {"name": "", "logo_url": "", "timezone": "UTC"},
}


def get_setting(db: Session, key: str) -> dict:
    row = db.get(SystemSetting, key)
    if row is None:
        return dict(DEFAULTS.get(key, {}))
    return row.value_json


def set_setting(db: Session, key: str, value: dict) -> SystemSetting:
    row = db.get(SystemSetting, key)
    now = dt.datetime.now(dt.timezone.utc)
    if row is None:
        row = SystemSetting(key=key, value_json=value, updated_at=now)
    else:
        row.value_json = value
        row.updated_at = now
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def is_globally_stopped(db: Session) -> bool:
    return bool(get_setting(db, GLOBAL_EMERGENCY_STOP_KEY).get("engaged"))


def engage_global_stop(db: Session, reason: str) -> None:
    set_setting(
        db,
        GLOBAL_EMERGENCY_STOP_KEY,
        {"engaged": True, "reason": reason, "engaged_at": dt.datetime.now(dt.timezone.utc).isoformat()},
    )


def disengage_global_stop(db: Session) -> None:
    set_setting(db, GLOBAL_EMERGENCY_STOP_KEY, {"engaged": False, "reason": "", "engaged_at": None})
