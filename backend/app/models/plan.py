import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel


class PlanStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class FeatureStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class FeatureType(str, Enum):
    core = "core"
    addon = "addon"


class Plan(SQLModel, table=True):
    """A commercial tier (BASIC / ESSENTIAL / ENTERPRISE). Data-driven — never
    branch application code on plan code directly; go through the
    entitlement/limit services instead."""

    __tablename__ = "plans"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(unique=True, index=True)  # BASIC | ESSENTIAL | ENTERPRISE
    name: str
    description: str | None = None
    setup_price: Decimal = Field(max_digits=12, decimal_places=2)
    annual_amc: Decimal = Field(max_digits=12, decimal_places=2)
    status: PlanStatus = Field(default=PlanStatus.active)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Feature(SQLModel, table=True):
    """Entry in the centralized feature catalog. Every gate in the app
    (backend `require_feature`, frontend `useFeature`) refers to `code`."""

    __tablename__ = "features"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    code: str = Field(unique=True, index=True)  # e.g. BARCODE_GENERATION
    name: str
    description: str | None = None
    module: str = Field(index=True)  # e.g. "inventory", "purchase", "sales"
    feature_type: FeatureType = Field(default=FeatureType.core)
    status: FeatureStatus = Field(default=FeatureStatus.active)


class PlanFeature(SQLModel, table=True):
    """Which features a plan enables by default. This table (plus
    TenantFeatureOverride) is the only place feature availability is decided
    — application code must never hard-code `if plan == "X"`."""

    __tablename__ = "plan_features"
    __table_args__ = (UniqueConstraint("plan_id", "feature_id", name="uq_plan_feature"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    plan_id: uuid.UUID = Field(foreign_key="plans.id", index=True)
    feature_id: uuid.UUID = Field(foreign_key="features.id", index=True)
    enabled: bool = Field(default=True)
    configuration_json: dict | None = Field(default=None, sa_column=Column(JSON))


class PlanLimit(SQLModel, table=True):
    """Default usage limit for a plan, e.g. MAX_USERS = 5. Read by
    `services/usage_limits.py::check_limit`, never inlined as a literal."""

    __tablename__ = "plan_limits"
    __table_args__ = (UniqueConstraint("plan_id", "limit_code", name="uq_plan_limit_code"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    plan_id: uuid.UUID = Field(foreign_key="plans.id", index=True)
    limit_code: str = Field(index=True)  # e.g. MAX_USERS, MAX_WAREHOUSES
    limit_value: int
