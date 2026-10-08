from __future__ import annotations

import bcrypt

# We call the `bcrypt` library directly rather than going through passlib:
# passlib's CryptContext does a version-sniffing check against
# bcrypt.__about__ that was removed in bcrypt>=4.1, which breaks on modern
# bcrypt releases (including on newer Python interpreters). bcrypt's own API
# is stable and small enough not to need the extra abstraction layer.

BCRYPT_MAX_INPUT_BYTES = 72  # bcrypt silently truncates beyond this; we reject longer inputs explicitly.


def hash_password(plain: str) -> str:
    encoded = plain.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_INPUT_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_INPUT_BYTES} bytes.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


MIN_PASSWORD_LENGTH = 12


def validate_password_policy(plain: str) -> list[str]:
    """Returns a list of policy violations (empty list == compliant)."""
    problems = []
    if len(plain) < MIN_PASSWORD_LENGTH:
        problems.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if not any(c.isupper() for c in plain):
        problems.append("Password must contain an uppercase letter.")
    if not any(c.islower() for c in plain):
        problems.append("Password must contain a lowercase letter.")
    if not any(c.isdigit() for c in plain):
        problems.append("Password must contain a digit.")
    if not any(not c.isalnum() for c in plain):
        problems.append("Password must contain a symbol.")
    return problems
