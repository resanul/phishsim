from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class TargetDefinition(BaseModel):
    recipient_ids: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ExclusionDefinition(BaseModel):
    recipient_ids: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    exclude_executives: bool = False
    exclude_test_accounts: bool = False
    exclude_service_accounts: bool = False


class CampaignCreate(BaseModel):
    name: str
    description: str = ""
    objective: str = ""
    campaign_type: str = "awareness"

    template_id: str
    landing_page_id: str
    sender_profile_id: str

    start_at: dt.datetime | None = None
    end_at: dt.datetime | None = None
    timezone: str = "UTC"

    sending_rate_per_minute: int = 10
    randomize_delivery_window_minutes: int = 0

    target_definition: TargetDefinition = Field(default_factory=TargetDefinition)
    exclusion_definition: ExclusionDefinition = Field(default_factory=ExclusionDefinition)

    authorized_organization: str
    approved_domains: list[str] = Field(default_factory=list)
    campaign_purpose: str

    test_mode: bool = True
    test_addresses: list[str] = Field(default_factory=list)

    retention_days: int = 180


class CampaignOut(BaseModel):
    id: str
    name: str
    description: str
    status: str
    campaign_type: str
    start_at: dt.datetime | None
    end_at: dt.datetime | None
    test_mode: bool
    kill_switch_engaged: bool

    class Config:
        from_attributes = True


class CampaignConfirmation(BaseModel):
    campaign_id: str
    recipient_count: int
    template_name: str
    landing_page_name: str
    start_at: dt.datetime | None
    end_at: dt.datetime | None
    sending_rate_per_minute: int
    estimated_duration_minutes: float
    test_mode: bool
    excluded_count: int


class KillSwitchRequest(BaseModel):
    reason: str
