from __future__ import annotations

import enum


class RoleName(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    SECURITY_ADMINISTRATOR = "security_administrator"
    CAMPAIGN_MANAGER = "campaign_manager"
    ANALYST = "analyst"
    READ_ONLY = "read_only"


class Permission(str, enum.Enum):
    CAMPAIGN_CREATE = "campaign:create"
    CAMPAIGN_LAUNCH = "campaign:launch"
    CAMPAIGN_MANAGE = "campaign:manage"
    RECIPIENT_MANAGE = "recipient:manage"
    TEMPLATE_MANAGE = "template:manage"
    REPORT_VIEW = "report:view"
    REPORT_GENERATE = "report:generate"
    SETTINGS_MANAGE = "settings:manage"
    USER_MANAGE = "user:manage"
    AUDIT_VIEW = "audit:view"
    ANALYTICS_VIEW = "analytics:view"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CampaignEventType(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERY_FAILED = "delivery_failed"
    OPENED = "opened"
    LINK_CLICKED = "link_clicked"
    LANDING_VISITED = "landing_visited"
    FORM_INTERACTED = "form_interacted"
    TRAINING_VIEWED = "training_viewed"
    SIMULATION_COMPLETED = "simulation_completed"
    REPORTED_PHISHING = "reported_phishing"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    NEEDS_TRAINING = "needs_training"


class ReportFormat(str, enum.Enum):
    PDF = "pdf"
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"


class AuditResult(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
