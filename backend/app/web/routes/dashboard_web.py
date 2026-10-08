from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi import Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import analytics_service
from app.web.deps import require_web_admin
from app.web.render import render_page

router = APIRouter(tags=["web-dashboard"])


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_admin)):
    kpis = analytics_service.dashboard_kpis(db)
    employees = analytics_service.employee_metrics(db)
    departments = analytics_service.department_metrics(db)
    return render_page(request, db, admin, "dashboard.html", kpis=kpis, employees=employees, departments=departments)
