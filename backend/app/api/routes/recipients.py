from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.enums import Permission
from app.models.identity import Administrator
from app.models.recipients import Recipient, RecipientGroup
from app.schemas.recipients import CSVImportResult, RecipientCreate, RecipientGroupCreate, RecipientOut
from app.services import recipients_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/api/recipients", tags=["recipients"])

MAX_CSV_BYTES = 5 * 1024 * 1024  # 5MB upload limit


@router.get("", response_model=list[RecipientOut])
def list_recipients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(require_permission(Permission.RECIPIENT_MANAGE)),
):
    limit = min(limit, 500)
    rows = db.execute(select(Recipient).where(Recipient.is_deleted.is_(False)).offset(skip).limit(limit)).scalars().all()
    return rows


@router.post("", response_model=RecipientOut, status_code=status.HTTP_201_CREATED)
def create_recipient(
    payload: RecipientCreate,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.RECIPIENT_MANAGE)),
):
    existing = db.execute(select(Recipient).where(Recipient.email == payload.email.lower())).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A recipient with this email already exists.")
    recipient = Recipient(**{**payload.model_dump(), "email": payload.email.lower()})
    db.add(recipient)
    db.commit()
    db.refresh(recipient)
    log_action(db, actor_id=actor.id, actor_email=actor.email, action="recipient_created", object_type="recipient", object_id=recipient.id)
    return recipient


@router.post("/import", response_model=CSVImportResult)
async def import_recipients_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.RECIPIENT_MANAGE)),
):
    if file.content_type not in ("text/csv", "application/vnd.ms-excel", "application/octet-stream", "text/plain"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV uploads are supported.")

    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV file too large (max 5MB).")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must be UTF-8 encoded.")

    result = recipients_service.import_csv(db, text)
    log_action(
        db,
        actor_id=actor.id,
        actor_email=actor.email,
        action="recipients_imported",
        object_type="recipient",
        metadata={"imported": result.imported, "duplicates": result.duplicates_skipped, "invalid": result.invalid_skipped},
    )
    return result


@router.post("/groups", status_code=status.HTTP_201_CREATED)
def create_group(
    payload: RecipientGroupCreate,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.RECIPIENT_MANAGE)),
):
    group = RecipientGroup(name=payload.name, description=payload.description)
    db.add(group)
    db.commit()
    db.refresh(group)
    log_action(db, actor_id=actor.id, actor_email=actor.email, action="recipient_group_created", object_type="recipient_group", object_id=group.id)
    return {"id": group.id, "name": group.name}


@router.delete("/{recipient_id}")
def delete_recipient(
    recipient_id: str,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.RECIPIENT_MANAGE)),
):
    recipient = db.get(Recipient, recipient_id)
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found.")
    recipient.is_deleted = True
    recipient.is_active = False
    db.add(recipient)
    db.commit()
    log_action(db, actor_id=actor.id, actor_email=actor.email, action="recipient_deleted", object_type="recipient", object_id=recipient.id)
    return {"deleted": True}
