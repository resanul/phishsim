from __future__ import annotations

import datetime as dt
import secrets
from typing import Any

import jwt

from app.config import settings


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.access_token_expire_minutes),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])


def generate_tracking_token() -> str:
    """Cryptographically random, non-guessable per-recipient tracking token."""
    return secrets.token_urlsafe(settings.tracking_token_bytes)
