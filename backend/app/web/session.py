"""Cookie-based session for the server-rendered dashboard.

The REST API (app/api/routes/*) authenticates with bearer JWTs and has no
concept of cookies or CSRF, which is appropriate for a token-based API.
The human-facing dashboard is a different trust boundary (browser + forms),
so it gets its own signed, httpOnly session cookie plus CSRF tokens on every
state-changing form -- standard practice for cookie-authenticated web UIs.
"""
from __future__ import annotations

import secrets
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

_serializer = URLSafeTimedSerializer(settings.secret_key, salt="phishsim-web-session")

SESSION_MAX_AGE_SECONDS = settings.access_token_expire_minutes * 60
CSRF_COOKIE_NAME = "phishsim_csrf"


def create_session_value(admin_id: str) -> str:
    return _serializer.dumps({"admin_id": admin_id})


def read_session_value(value: str) -> Optional[str]:
    try:
        data = _serializer.loads(value, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("admin_id")


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)
