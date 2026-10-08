from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Depends, Form, HTTPException, Request, status
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.database import get_db
from app.models.enums import Permission
from app.models.identity import Administrator
from app.services.rbac import role_has_permission
from app.web.session import CSRF_COOKIE_NAME, read_session_value

SESSION_COOKIE_NAME = "phishsim_web_session"


class RedirectToLogin(Exception):
    def __init__(self, next_path: str = "/") -> None:
        self.next_path = next_path


def get_web_admin(request: Request, db: Session = Depends(get_db)) -> Optional[Administrator]:
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw:
        return None
    admin_id = read_session_value(raw)
    if not admin_id:
        return None
    admin = db.get(Administrator, admin_id)
    if admin is None or not admin.is_active:
        return None
    return admin


def require_web_admin(request: Request, db: Session = Depends(get_db)) -> Administrator:
    admin = get_web_admin(request, db)
    if admin is None:
        raise RedirectToLogin(next_path=str(request.url.path))
    return admin


def require_web_permission(permission: Permission):
    def _checker(request: Request, db: Session = Depends(get_db)) -> Administrator:
        admin = require_web_admin(request, db)
        if not admin.is_super_admin and not role_has_permission(admin.role.name, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {permission.value}")
        return admin

    return _checker


def csrf_protect(request: Request, csrf_token: str = Form(...)) -> None:
    """FastAPI dependency: validates the hidden csrf_token form field against
    the signed csrf cookie set when the page was rendered. Implemented as a
    dependency (not middleware) so the request body is parsed exactly once
    by FastAPI's normal Form() machinery -- reading the body twice (once in
    a middleware, once in the handler) silently drops the body for
    downstream Starlette request objects."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_token or not hmac.compare_digest(cookie_token, csrf_token or ""):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid. Please reload the page and try again.")
