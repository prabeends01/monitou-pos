from datetime import date

from pydantic import BaseModel


class LimitUsage(BaseModel):
    used: int
    max: int


class FeatureInfo(BaseModel):
    """Plan-static — same for every tenant. Lets the frontend's locked-
    feature card show "available in Essential and Enterprise plans"
    without re-deriving plan/feature mappings client-side."""

    name: str
    module: str
    required_plan: str | None
    message: str


class SubscriptionInfo(BaseModel):
    """The tenant's current commercial term — CLAUDE.md Section 11.8.
    `status` here is the full ACTIVE/EXPIRING/EXPIRED/SUSPENDED/
    GRACE_PERIOD lifecycle (Subscription.status), distinct from
    `TenantEntitlementsResponse.tenant_status` (Tenant.status, just
    active/suspended) — the two lands at different stages and answer
    different questions (is this *account* usable at all, vs. where is
    this *commercial term* in its lifecycle)."""

    status: str
    start_date: date
    end_date: date | None
    renewal_date: date | None
    setup_fee: str
    annual_amc: str


class TenantEntitlementsResponse(BaseModel):
    """Everything the frontend needs to gate UI and render the Plan &
    Subscription page without re-deriving plan logic itself — fetched once
    per session by `useFeature`/`FeatureGate`/`PlanSubscription` (Stages
    6/9). `subscription` is `None` for a tenant that predates Stage 9's
    subscription-row backfill (or a freshly-created one with no
    subscription yet) — the frontend must handle that, not assume it's
    always present."""

    tenant_code: str
    company_name: str
    plan_code: str | None
    plan_name: str | None
    tenant_status: str
    subscription: SubscriptionInfo | None
    features: dict[str, bool]
    feature_info: dict[str, FeatureInfo]
    limits: dict[str, LimitUsage]
