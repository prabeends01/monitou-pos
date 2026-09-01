import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class PlatformAdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DashboardStats(BaseModel):
    total_tenants: int
    active_tenants: int
    suspended_accounts: int
    basic_customers: int
    essential_customers: int
    enterprise_customers: int
    amc_due: int  # renewal_date already in the past and still ACTIVE/EXPIRING
    upcoming_renewals: int  # renewal_date within the configurable lookahead window
    pending_upgrade_requests: int


class TenantListRow(BaseModel):
    id: uuid.UUID
    company_name: str
    tenant_code: str
    plan_code: str | None
    users_used: int
    users_max: int | None
    skus_used: int
    skus_max: int | None
    subscription_status: str | None
    amc_renewal_date: date | None
    tenant_status: str


class TenantUserRow(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    is_active: bool


class TenantDetail(BaseModel):
    id: uuid.UUID
    company_name: str
    tenant_code: str
    tenant_status: str
    plan_code: str | None
    plan_name: str | None
    features: dict[str, bool]
    limits: dict[str, dict[str, int]]
    subscription_status: str | None
    subscription_start_date: date | None
    subscription_renewal_date: date | None
    annual_amc: str | None
    users: list[TenantUserRow]


class ExceededLimit(BaseModel):
    limit_code: str
    current_usage: int
    new_limit: int


class LostFeature(BaseModel):
    code: str
    name: str


class PlanChangeImpact(BaseModel):
    """CLAUDE.md's downgrade-impact check (Stage 13) — what would actually
    happen if this tenant moved to `target_plan_code`, computed WITHOUT
    changing anything. Empty `exceeded_limits`/`lost_features` means the
    move is safe to apply with no confirmation needed (always true for a
    plain upgrade; can also be true for a downgrade if the tenant's usage
    already fits, or overrides cover the gap)."""

    target_plan_code: str
    is_downgrade: bool
    exceeded_limits: list[ExceededLimit]
    lost_features: list[LostFeature]


class ChangePlanRequest(BaseModel):
    plan_code: str
    reason: str
    # required when `plan-change-impact` for this plan_code is non-empty —
    # see routers/platform_admin.py::change_plan. Defaults False so a caller
    # can't skip the check by omitting the field.
    confirm: bool = False


class FeatureOverrideRequest(BaseModel):
    feature_code: str
    enabled: bool
    reason: str


class LimitOverrideRequest(BaseModel):
    limit_code: str
    override_value: int
    reason: str


class RevokePlanRequest(BaseModel):
    reason: str


class SuspendRequest(BaseModel):
    reason: str


class ReactivateRequest(BaseModel):
    reason: str


class ExtendSubscriptionRequest(BaseModel):
    new_renewal_date: date
    reason: str


class UpgradeRequestAdminRow(BaseModel):
    """A pending (or decided) upgrade request, from Platform Admin's
    cross-tenant view — CLAUDE.md Stage 10/11: without this, a request
    only ever surfaced if an admin happened to open that exact tenant and
    change its plan; nothing told them one existed."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    tenant_code: str
    company_name: str
    requested_plan_code: str
    requested_by_username: str | None
    note: str | None
    status: str
    requested_at: datetime


class ApproveUpgradeRequestRequest(BaseModel):
    reason: str
    # same meaning as ChangePlanRequest.confirm — approving a request that
    # would exceed a limit or drop a feature still needs an explicit nod.
    confirm: bool = False


class RejectUpgradeRequestRequest(BaseModel):
    reason: str


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    platform_admin_username: str
    action: str
    tenant_id: uuid.UUID | None
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    reason: str | None
    created_at: datetime
