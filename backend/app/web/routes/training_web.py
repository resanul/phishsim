from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.campaigns import TrainingSession
from app.models.enums import Permission
from app.web.deps import require_web_permission
from app.web.render import render_page

router = APIRouter(prefix="/training", tags=["web-training"])


@router.get("")
def training_page(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.ANALYTICS_VIEW))):
    sessions = db.execute(select(TrainingSession).order_by(TrainingSession.started_at.desc()).limit(100)).scalars().all()
    completed = sum(1 for s in sessions if s.completed_at is not None)
    return render_page(request, db, admin, "training.html", sessions=sessions, completed=completed)
