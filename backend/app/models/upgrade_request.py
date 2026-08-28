import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class UpgradeRequestStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class UpgradeRequest(SQLModel, table=True):
    """A tenant admin's request to move to a different plan — CLAUDE.md's
    Upgrade Comparison Screen: "Upgrade action should generate an upgrade
    request rather than automatically changing the plan." Reviewing/acting
    on these (approve -> actually change `Tenant.active_plan_id`, reject,
    etc.) is Platform Admin's job, Stage 11+ — this stage only creates and
    lists them."""

    __tablename__ = "upgrade_requests"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenants.id", index=True)
    requested_plan_id: uuid.UUID = Field(foreign_key="plans.id")
    requested_by: uuid.UUID = Field(foreign_key="users.id")
    status: UpgradeRequestStatus = Field(default=UpgradeRequestStatus.pending, index=True)
    note: str | None = Field(default=None)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = Field(default=None)
    # the platform admin who approved/rejected it — a different actor type
    # than `requested_by` above, hence a different table (Section 11.13).
    decided_by: uuid.UUID | None = Field(default=None, foreign_key="platform_admins.id")
