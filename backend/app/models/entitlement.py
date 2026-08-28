import uuid
from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel


class TenantFeatureOverride(SQLModel, table=True):
    """Per-tenant exception to the plan's default feature set — e.g. a Basic
    customer who bought Barcode as a paid add-on, without moving the whole
    tenant to Essential. `enabled=True` grants a feature the plan withholds;
    `enabled=False` revokes one the plan grants. Always the more specific
    layer: entitlement resolution is override > plan default."""

    __tablename__ = "tenant_feature_overrides"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenants.id", index=True)
    feature_id: uuid.UUID = Field(foreign_key="features.id", index=True)
    enabled: bool
    configuration_json: dict | None = Field(default=None, sa_column=Column(JSON))
    reason: str
    # Stage 11 correction: overrides are exclusively a Platform Admin action
    # (CLAUDE.md Section 11.13), so this must reference platform_admins, not
    # tenant users — fixed via a Stage 11 migration before any real data was
    # ever written to this column.
    approved_by: uuid.UUID = Field(foreign_key="platform_admins.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TenantLimitOverride(SQLModel, table=True):
    """Per-tenant exception to a plan limit, e.g. MAX_USERS raised 5 -> 8 for
    one customer. `check_limit` must always check this before falling back
    to `PlanLimit`."""

    __tablename__ = "tenant_limit_overrides"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenants.id", index=True)
    limit_code: str = Field(index=True)
    override_value: int
    reason: str
    # Stage 11 correction: overrides are exclusively a Platform Admin action
    # (CLAUDE.md Section 11.13), so this must reference platform_admins, not
    # tenant users — fixed via a Stage 11 migration before any real data was
    # ever written to this column.
    approved_by: uuid.UUID = Field(foreign_key="platform_admins.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UsageCounter(SQLModel, table=True):
    """Current count for a tenant against a limit_code (MAX_USERS,
    MAX_WAREHOUSES, MAX_SKUS, MAX_BRANCHES, ...). Maintained by the services
    that create/deactivate the counted entities — never derive it ad hoc with
    a COUNT(*) scattered across routers; one write path per metric."""

    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("tenant_id", "metric_code", name="uq_tenant_metric"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenants.id", index=True)
    metric_code: str = Field(index=True)
    current_value: int = Field(default=0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
