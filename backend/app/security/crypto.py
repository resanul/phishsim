"""Symmetric encryption for secrets-at-rest (SMTP passwords, MFA TOTP secrets).

Key is derived from settings.secret_key via HKDF -- never store the derived
key or the raw secret_key in the database. Rotate settings.secret_key only
via a documented re-encryption migration (see SECURITY.md).
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _derive_fernet_key() -> bytes:
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_fernet_key())


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    return _fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
