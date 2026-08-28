import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlmodel import Field, SQLModel


class TenantStatus(str, Enum):
    active = "active"
    suspended = "suspended"


class SubscriptionStatus(str, Enum):
    active = "ACTIVE"
    expiring = "EXPIRING"
    expired = "EXPIRED"
    suspended = "SUSPENDED"
    grace_period = "GRACE_PERIOD"


class Tenant(SQLModel, table=True):
    """A customer/organization. Every business record belongs to exactly one
    tenant via a `tenant_id` FK — see Section 11.2 of CLAUDE.md for the
    isolation strategy. `active_plan_id` is a cache of the current
    subscription's plan for fast reads; `subscriptions` remains the source
    of truth for history/dates/status."""

    __tablename__ = "tenants"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_code: str = Field(unique=True, index=True)
    company_name: str
    active_plan_id: uuid.UUID | None = Field(default=None, foreign_key="plans.id")
    status: TenantStatus = Field(default=TenantStatus.active)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Subscription(SQLModel, table=True):
    """One commercial term for a tenant. A tenant may have a history of
    subscriptions (renewals, plan changes); the current one is whichever has
    the latest `start_date` with no later row, and its `plan_id` should match
    `Tenant.active_plan_id`."""

    __tablename__ = "subscriptions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenants.id", index=True)
    plan_id: uuid.UUID = Field(foreign_key="plans.id", index=True)
    start_date: date
    end_date: date | None = None
    status: SubscriptionStatus = Field(default=SubscriptionStatus.active)
    setup_fee: Decimal = Field(max_digits=12, decimal_places=2)
    annual_amc: Decimal = Field(max_digits=12, decimal_places=2)
    renewal_date: date | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
