from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.audit import AuditLog
from app.models.enums import Permission
from app.services.audit_service import verify_chain

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get("")
def list_audit_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(require_permission(Permission.AUDIT_VIEW)),
):
    limit = min(limit, 500)
    rows = db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)).scalars().all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "actor_email": r.actor_email,
            "action": r.action,
            "object_type": r.object_type,
            "object_id": r.object_id,
            "source_ip": r.source_ip,
            "result": r.result,
        }
        for r in rows
    ]


@router.get("/verify")
def verify_audit_chain(db: Session = Depends(get_db), _=Depends(require_permission(Permission.AUDIT_VIEW))):
    ok, message = verify_chain(db)
    return {"intact": ok, "message": message}
