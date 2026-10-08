from __future__ import annotations

from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.models.identity import Administrator
from app.services import settings_service
from app.web.session import CSRF_COOKIE_NAME, generate_csrf_token


def base_context(request: Request, db: Session, admin: Optional[Administrator], **extra) -> dict:
    ctx = {
        "request": request,
        "current_admin": admin,
        "csrf_token": generate_csrf_token(),
        "emergency_engaged": settings_service.is_globally_stopped(db),
    }
    ctx.update(extra)
    return ctx


def attach_csrf_cookie(response: Response, ctx: dict) -> Response:
    response.set_cookie(
        CSRF_COOKIE_NAME,
        ctx["csrf_token"],
        httponly=True,
        samesite="lax",
        max_age=3600,
    )
    return response
