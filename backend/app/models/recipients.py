from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import Boolean, ForeignKey, String, Table, Column, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin

recipient_group_members = Table(
    "recipient_group_members",
    Base.metadata,
    Column("recipient_id", ForeignKey("recipients.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", ForeignKey("recipient_groups.id", ondelete="CASCADE"), primary_key=True),
)


class RecipientGroup(Base, TimestampMixin):
    __tablename__ = "recipient_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    members: Mapped[List["Recipient"]] = relationship(
        secondary=recipient_group_members, back_populates="groups"
    )


class Recipient(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "recipients"
    __table_args__ = (UniqueConstraint("email", name="uq_recipient_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    job_title: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    manager: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    exclusion_reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_test_address: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    custom_attributes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    groups: Mapped[List["RecipientGroup"]] = relationship(
        secondary=recipient_group_members, back_populates="members"
    )

    @property
    def domain(self) -> str:
        return self.email.rsplit("@", 1)[-1].lower() if "@" in self.email else ""
