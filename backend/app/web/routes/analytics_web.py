from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import Permission
from app.services import analytics_service
from app.web.deps import require_web_permission
from app.web.render import render_page

router = APIRouter(prefix="/analytics", tags=["web-analytics"])


@router.get("")
def analytics_page(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.ANALYTICS_VIEW))):
    kpis = analytics_service.dashboard_kpis(db)
    employees = analytics_service.employee_metrics(db)
    departments = analytics_service.department_metrics(db)
    return render_page(request, db, admin, "analytics.html", kpis=kpis, employees=employees, departments=departments)
