from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.enums import Permission
from app.models.identity import Administrator
from app.services import settings_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/{key}")
def get_setting(key: str, db: Session = Depends(get_db), _=Depends(require_permission(Permission.SETTINGS_MANAGE))):
    return settings_service.get_setting(db, key)


@router.put("/{key}")
def put_setting(
    key: str,
    value: dict,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.SETTINGS_MANAGE)),
):
    row = settings_service.set_setting(db, key, value)
    log_action(db, actor_id=actor.id, actor_email=actor.email, action="settings_changed", object_type="system_setting", object_id=key, metadata={"value": value})
    return {"key": row.key, "value": row.value_json}
