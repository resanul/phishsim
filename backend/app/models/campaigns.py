from __future__ import annotations

from typing import Optional

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import CampaignStatus, CampaignEventType
from app.models.mixins import TimestampMixin


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    objective: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    campaign_type: Mapped[str] = mapped_column(String(64), nullable=False, default="awareness")

    template_id: Mapped[str] = mapped_column(ForeignKey("email_templates.id"), nullable=False)
    landing_page_id: Mapped[str] = mapped_column(ForeignKey("landing_pages.id"), nullable=False)
    sender_profile_id: Mapped[str] = mapped_column(ForeignKey("sender_profiles.id"), nullable=False)

    template = relationship("EmailTemplate")
    landing_page = relationship("LandingPage")
    sender_profile = relationship("SenderProfile")

    status: Mapped[str] = mapped_column(String(32), default=CampaignStatus.DRAFT.value, nullable=False, index=True)

    start_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    sending_rate_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    randomize_delivery_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Targeting definition, stored declaratively so it can be re-evaluated / audited.
    target_definition: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    exclusion_definition: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Authorization & Safety (spec section 28)
    owner_admin_id: Mapped[str] = mapped_column(ForeignKey("administrators.id"), nullable=False)
    authorized_organization: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    approved_domains: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    campaign_purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")

    test_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    test_addresses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    kill_switch_engaged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kill_switch_engaged_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    kill_switch_reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=180)

    targets: Mapped[list["CampaignTarget"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    events: Mapped[list["CampaignEvent"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")


class CampaignTarget(Base, TimestampMixin):
    """A resolved recipient assigned to a campaign, with its unique unguessable tracking token."""

    __tablename__ = "campaign_targets"
    __table_args__ = (Index("ix_campaign_targets_campaign_token", "campaign_id", "tracking_token", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("recipients.id"), nullable=False)

    campaign: Mapped["Campaign"] = relationship(back_populates="targets")
    recipient = relationship("Recipient")

    tracking_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    queued_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    send_error: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    scheduled_send_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    clicked_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reported_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    training_completed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    interaction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CampaignEvent(Base, TimestampMixin):
    """Append-only event log for a campaign target. This IS the safe tracking data --
    it intentionally excludes any real credentials, cookies, tokens, or form contents."""

    __tablename__ = "campaign_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    target_id: Mapped[str] = mapped_column(ForeignKey("campaign_targets.id", ondelete="CASCADE"), nullable=False)

    campaign: Mapped["Campaign"] = relationship(back_populates="events")

    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class TrainingSession(Base, TimestampMixin):
    __tablename__ = "training_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    target_id: Mapped[str] = mapped_column(ForeignKey("campaign_targets.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    module_key: Mapped[str] = mapped_column(String(64), nullable=False, default="red_flags_overview")
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
