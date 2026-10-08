from __future__ import annotations

import datetime as dt
import hashlib
import uuid

from sqlalchemy import DateTime, ForeignKey, String, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """Tamper-resistant, append-only audit trail.

    Tamper resistance is implemented via a hash chain: each record's
    `record_hash` is a SHA-256 digest over its own fields plus the previous
    record's hash (`prev_hash`). Any historical edit breaks the chain and is
    detectable by app.services.audit.verify_chain().
    """

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    object_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    result: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    def compute_hash(self) -> str:
        # Normalize to a fixed UTC representation before hashing: the DB
        # session/connection may hand back the same instant with a
        # different tzinfo (e.g. server timezone) than the one this process
        # constructed it with, and the hash must be invariant to that.
        if self.timestamp is not None:
            ts = self.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=dt.timezone.utc)
            timestamp_str = ts.astimezone(dt.timezone.utc).isoformat()
        else:
            timestamp_str = ""

        payload = "|".join(
            [
                self.id,
                timestamp_str,
                self.actor_id,
                self.action,
                self.object_type,
                self.object_id,
                self.result,
                self.prev_hash,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
