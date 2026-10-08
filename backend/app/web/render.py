from __future__ import annotations

import os
from typing import Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.responses import Response

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def fmt_dt(value) -> str:
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d %H:%M UTC")


def fmt_pct(value) -> str:
    if value is None:
        return "—"
    return f"{value}%"


templates.env.filters["fmt_dt"] = fmt_dt
templates.env.filters["fmt_pct"] = fmt_pct


def render_page(request: Request, db: Session, admin, template_name: str, status_code: int = 200, **extra) -> Response:
    from app.web.context import attach_csrf_cookie, base_context

    ctx = base_context(request, db, admin, **extra)
    response = templates.TemplateResponse(template_name, ctx, status_code=status_code)
    return attach_csrf_cookie(response, ctx)
