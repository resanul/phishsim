"""Import all models so Base.metadata is fully populated for Alembic autogenerate
and for create_all() in tests/dev bootstrapping."""

from app.models.identity import Permission, Role, Administrator  # noqa: F401
from app.models.recipients import Recipient, RecipientGroup  # noqa: F401
from app.models.content import SenderProfile, EmailTemplate, LandingPage  # noqa: F401
from app.models.campaigns import Campaign, CampaignTarget, CampaignEvent, TrainingSession  # noqa: F401
from app.models.audit import AuditLog, SystemSetting  # noqa: F401
from app.models.reports import Report  # noqa: F401
