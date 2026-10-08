from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.models.campaigns import Campaign
from app.models.enums import Permission
from app.models.reports import Report
from app.services import reporting_service
from app.services.audit_service import log_action
from app.web.deps import csrf_protect, require_web_permission
from app.web.render import render_page

router = APIRouter(prefix="/reports", tags=["web-reports"])


@router.get("")
def list_reports(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.REPORT_VIEW))):
    rows = db.execute(select(Report).order_by(Report.generated_at.desc())).scalars().all()
    campaigns = db.execute(select(Campaign)).scalars().all()
    return render_page(request, db, admin, "reports/list.html", items=rows, campaigns=campaigns)


@router.post("/generate")
def generate_report(
    db: Session = Depends(get_db),
    admin=Depends(require_web_permission(Permission.REPORT_GENERATE)),
    fmt: str = Form(...),
    campaign_id: str = Form(""),
    _csrf=Depends(csrf_protect),
):
    campaign = db.get(Campaign, campaign_id) if campaign_id else None
    report = reporting_service.generate_report(db, fmt, generated_by=admin.id, campaign=campaign)
    log_action(db, actor_id=admin.id, actor_email=admin.email, action="report_generated", object_type="report", object_id=report.id, metadata={"format": fmt, "via": "web"})
    return RedirectResponse("/reports?msg=Report+generated.", status_code=303)


@router.get("/{report_id}/download")
def download_report(report_id: str, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.REPORT_VIEW))):
    report = db.get(Report, report_id)
    return FileResponse(report.file_path, filename=f"report_{report.id[:8]}.{report.format}")
