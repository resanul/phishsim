from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.models.content import EmailTemplate
from app.models.enums import Permission
from app.services.content_service import validate_template
from app.web.deps import csrf_protect, require_web_permission
from app.web.render import render_page

router = APIRouter(prefix="/templates", tags=["web-templates"])


@router.get("")
def list_templates(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.TEMPLATE_MANAGE))):
    rows = db.execute(select(EmailTemplate).order_by(EmailTemplate.created_at.desc())).scalars().all()
    return render_page(request, db, admin, "templates/list.html", items=rows)


@router.get("/new")
def new_template_form(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.TEMPLATE_MANAGE))):
    return render_page(request, db, admin, "templates/new.html", validation=None)


@router.post("/new")
def create_template(
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(require_web_permission(Permission.TEMPLATE_MANAGE)),
    name: str = Form(...),
    scenario: str = Form("custom"),
    subject: str = Form(...),
    from_name: str = Form(""),
    html_body: str = Form(...),
    text_body: str = Form(""),
    _csrf=Depends(csrf_protect),
):
    from app.api.routes.content import sanitize_html

    validation = validate_template(subject, html_body, text_body)
    if not validation.is_valid:
        return render_page(
            request, db, admin, "templates/new.html", status_code=400,
            validation=validation, name=name, scenario=scenario, subject=subject, from_name=from_name, html_body=html_body, text_body=text_body,
        )

    template = EmailTemplate(
        name=name, scenario=scenario, subject=subject, from_name=from_name,
        html_body=sanitize_html(html_body), text_body=text_body,
    )
    db.add(template)
    db.commit()
    return RedirectResponse("/templates?msg=Template+created.", status_code=303)
