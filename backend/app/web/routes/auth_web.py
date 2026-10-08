from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.config import settings
from app.database import get_db
from app.web.deps import SESSION_COOKIE_NAME, csrf_protect, get_web_admin
from app.web.render import render_page
from app.services import auth_service

router = APIRouter(tags=["web-auth"])


@router.get("/login")
def login_form(request: Request, db: Session = Depends(get_db)):
    admin = get_web_admin(request, db)
    if admin is not None:
        return RedirectResponse("/", status_code=303)
    return render_page(request, db, None, "login.html", mfa_required=False, email="")


@router.post("/login")
def login_submit(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
    totp_code: str = Form(""),
    _csrf=Depends(csrf_protect),
):
    from app.api.deps import get_client_ip

    admin, mfa_required, error = auth_service.authenticate(
        db, email, password, totp_code or None, source_ip=get_client_ip(request)
    )
    if admin is None:
        return render_page(
            request, db, None, "login.html",
            status_code=401,
            mfa_required=mfa_required,
            email=email,
            error=error or ("Enter your MFA code to continue." if mfa_required else "Invalid credentials."),
        )

    from app.web.session import create_session_value

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_value(admin.id),
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response
