from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.enums import AuditResult


def log_action(
    db: Session,
    *,
    actor_id: str = "system",
    actor_email: str = "system",
    action: str,
    object_type: str = "",
    object_id: str = "",
    source_ip: str = "",
    result: str = AuditResult.SUCCESS.value,
    metadata: dict | None = None,
) -> AuditLog:
    prev = db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(1)).scalar_one_or_none()
    prev_hash = prev.record_hash if prev else ""

    entry = AuditLog(
        id=str(uuid.uuid4()),
        timestamp=dt.datetime.now(dt.timezone.utc),
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        object_type=object_type,
        object_id=object_id,
        source_ip=source_ip,
        result=result,
        metadata_json=metadata or {},
        prev_hash=prev_hash,
    )
    entry.record_hash = entry.compute_hash()
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def verify_chain(db: Session) -> tuple[bool, str]:
    """Walk the audit log in insertion order and verify the hash chain is intact."""
    rows = db.execute(select(AuditLog).order_by(AuditLog.timestamp.asc())).scalars().all()
    prev_hash = ""
    for row in rows:
        if row.prev_hash != prev_hash:
            return False, f"chain broken before record {row.id}"
        if row.compute_hash() != row.record_hash:
            return False, f"record {row.id} hash mismatch (possible tampering)"
        prev_hash = row.record_hash
    return True, "ok"
