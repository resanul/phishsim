from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.models.content import LandingPage
from app.models.enums import Permission
from app.web.deps import csrf_protect, require_web_permission
from app.web.render import render_page

router = APIRouter(prefix="/landing-pages", tags=["web-landing-pages"])


@router.get("")
def list_landing_pages(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.TEMPLATE_MANAGE))):
    rows = db.execute(select(LandingPage).order_by(LandingPage.created_at.desc())).scalars().all()
    return render_page(request, db, admin, "landing_pages/list.html", items=rows)


@router.get("/new")
def new_landing_page_form(request: Request, db: Session = Depends(get_db), admin=Depends(require_web_permission(Permission.TEMPLATE_MANAGE))):
    return render_page(request, db, admin, "landing_pages/new.html")


@router.post("/new")
def create_landing_page(
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(require_web_permission(Permission.TEMPLATE_MANAGE)),
    name: str = Form(...),
    html_body: str = Form(...),
    has_synthetic_form: str = Form(""),
    show_education_reveal: str = Form("on"),
    _csrf=Depends(csrf_protect),
):
    from app.api.routes.content import sanitize_html

    page = LandingPage(
        name=name,
        html_body=sanitize_html(html_body),
        has_synthetic_form=(has_synthetic_form == "on"),
        show_education_reveal=(show_education_reveal == "on"),
    )
    db.add(page)
    db.commit()
    return RedirectResponse("/landing-pages?msg=Landing+page+created.", status_code=303)
