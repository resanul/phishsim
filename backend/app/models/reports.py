from __future__ import annotations

from typing import Optional

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[Optional[str]] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    generated_by: Mapped[str] = mapped_column(ForeignKey("administrators.id"), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    parameters_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
