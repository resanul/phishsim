from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.enums import Permission
from app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _=Depends(require_permission(Permission.ANALYTICS_VIEW))):
    return {
        "kpis": analytics_service.dashboard_kpis(db),
        "employees": analytics_service.employee_metrics(db),
        "departments": analytics_service.department_metrics(db),
    }


@router.get("/departments")
def departments(db: Session = Depends(get_db), _=Depends(require_permission(Permission.ANALYTICS_VIEW))):
    return analytics_service.department_metrics(db)
