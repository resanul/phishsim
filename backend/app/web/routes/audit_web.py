from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit import AuditLog
from app.models.enums import Permission
from app.services.audit_service import verify_chain
from app.web.deps import require_web_permission
from app.web.render import render_page

router = APIRouter(prefix="/audit-logs", tags=["web-audit"])


@router.get("")
def list_audit_logs(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.AUDIT_VIEW))):
    rows = db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(200)).scalars().all()
    ok, message = verify_chain(db)
    return render_page(request, db, admin, "audit/list.html", items=rows, chain_ok=ok, chain_message=message)
