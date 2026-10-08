from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class SenderProfile(Base, TimestampMixin):
    """Per-campaign sender identity used for simulated emails."""

    __tablename__ = "sender_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    from_name: Mapped[str] = mapped_column(String(120), nullable=False)
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    reply_to: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    smtp_port: Mapped[int] = mapped_column(default=587, nullable=False)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    smtp_username: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # NOTE: smtp_password is never stored in plaintext in this column; it is
    # stored encrypted-at-rest via app.security.crypto.encrypt_secret().
    smtp_password_encrypted: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EmailTemplate(Base, TimestampMixin):
    __tablename__ = "email_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False, default="custom")
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    from_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    reply_to: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    html_body: Mapped[str] = mapped_column(Text, nullable=False)
    text_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LandingPage(Base, TimestampMixin):
    __tablename__ = "landing_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    html_body: Mapped[str] = mapped_column(Text, nullable=False)
    # Whether this page includes a synthetic demo form. If true, submitted
    # values are NEVER persisted -- see app.services.landing_pages.
    has_synthetic_form: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    show_education_reveal: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
