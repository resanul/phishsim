from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.campaigns import Campaign
from app.models.enums import Permission
from app.models.identity import Administrator
from app.models.reports import Report
from app.services import reporting_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
def list_reports(db: Session = Depends(get_db), _=Depends(require_permission(Permission.REPORT_VIEW))):
    rows = db.execute(select(Report)).scalars().all()
    return [{"id": r.id, "campaign_id": r.campaign_id, "format": r.format, "generated_at": r.generated_at} for r in rows]


@router.post("/generate")
def generate_report(
    fmt: str,
    campaign_id: str | None = None,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.REPORT_GENERATE)),
):
    if fmt not in reporting_service.GENERATORS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported format '{fmt}'. Use one of: {list(reporting_service.GENERATORS)}")

    campaign = None
    if campaign_id:
        campaign = db.get(Campaign, campaign_id)
        if campaign is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    report = reporting_service.generate_report(db, fmt, generated_by=actor.id, campaign=campaign)
    log_action(db, actor_id=actor.id, actor_email=actor.email, action="report_generated", object_type="report", object_id=report.id, metadata={"format": fmt, "campaign_id": campaign_id})
    return {"id": report.id, "format": report.format, "generated_at": report.generated_at}


@router.get("/{report_id}/download")
def download_report(report_id: str, db: Session = Depends(get_db), _=Depends(require_permission(Permission.REPORT_VIEW))):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return FileResponse(report.file_path, filename=f"report.{report.format}")
