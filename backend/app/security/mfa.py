from __future__ import annotations

import pyotp

from app.security.crypto import decrypt_secret, encrypt_secret


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def encrypt_totp_secret(secret: str) -> str:
    return encrypt_secret(secret)


def get_provisioning_uri(secret: str, account_email: str, issuer: str = "PhishSim") -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=issuer)


def verify_totp(encrypted_secret: str, code: str) -> bool:
    if not encrypted_secret or not code:
        return False
    secret = decrypt_secret(encrypted_secret)
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
