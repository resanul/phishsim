from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.models.enums import Permission
from app.models.recipients import Recipient
from app.services import recipients_service
from app.web.deps import csrf_protect, require_web_permission
from app.web.render import render_page

router = APIRouter(prefix="/recipients", tags=["web-recipients"])
MAX_CSV_BYTES = 5 * 1024 * 1024


@router.get("")
def list_recipients(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.RECIPIENT_MANAGE))):
    rows = db.execute(select(Recipient).where(Recipient.is_deleted.is_(False)).order_by(Recipient.created_at.desc()).limit(200)).scalars().all()
    return render_page(request, db, admin, "recipients/list.html", items=rows)


@router.post("/add")
def add_recipient(
    db: Session = Depends(get_db),
    admin=Depends(require_web_permission(Permission.RECIPIENT_MANAGE)),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    department: str = Form(""),
    job_title: str = Form(""),
    _csrf=Depends(csrf_protect),
):
    existing = db.execute(select(Recipient).where(Recipient.email == email.lower())).scalar_one_or_none()
    if existing is None:
        db.add(Recipient(first_name=first_name, last_name=last_name, email=email.lower(), department=department, job_title=job_title))
        db.commit()
        return RedirectResponse("/recipients?msg=Recipient+added.", status_code=303)
    return RedirectResponse("/recipients?error=A+recipient+with+this+email+already+exists.", status_code=303)


@router.post("/import")
async def import_csv(
    db: Session = Depends(get_db),
    admin=Depends(require_web_permission(Permission.RECIPIENT_MANAGE)),
    file: UploadFile = File(...),
    _csrf=Depends(csrf_protect),
):
    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        return RedirectResponse("/recipients?error=CSV+too+large+(max+5MB).", status_code=303)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return RedirectResponse("/recipients?error=CSV+must+be+UTF-8+encoded.", status_code=303)

    result = recipients_service.import_csv(db, text)
    msg = f"Imported {result.imported}, skipped {result.duplicates_skipped} duplicate(s) and {result.invalid_skipped} invalid row(s)."
    return RedirectResponse(f"/recipients?msg={msg}", status_code=303)
