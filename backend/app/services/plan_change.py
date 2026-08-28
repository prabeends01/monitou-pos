"""Downgrade-impact assessment — CLAUDE.md Stage 13: "Create a
downgrade-impact check before allowing plan reduction." Computes what
would actually change if a tenant moved to a different plan, without
changing anything — `TenantLimitOverride`/`TenantFeatureOverride` rows are
respected exactly as `usage_limits.check_limit`/`entitlements.can_use_feature`
already do, since those overrides survive a plan change unchanged (they're
tenant-level exceptions, not plan-level defaults).

Deliberately plan-direction-agnostic: an upgrade normally comes back empty
(nothing to lose), but the same function is what proves that — it isn't
special-cased to skip the check for upgrades, so a surprising edge case
(e.g. a tenant with a feature override the new plan doesn't need but some
other override conflicts with) still gets caught.
"""

import uuid

from sqlmodel import Session, select

from app.models.entitlement import TenantFeatureOverride, TenantLimitOverride
from app.models.plan import Feature, Plan, PlanFeature, PlanLimit
from app.models.tenant import Tenant
from app.plan_catalog import PLAN_LIMITS
from app.services.entitlements import can_use_feature
from app.services.usage_limits import get_usage


def _effective_limit_under_plan(session: Session, tenant_id: uuid.UUID, plan_id: uuid.UUID, limit_code: str) -> int | None:
    override = session.exec(
        select(TenantLimitOverride).where(
            TenantLimitOverride.tenant_id == tenant_id, TenantLimitOverride.limit_code == limit_code
        )
    ).first()
    if override is not None:
        return override.override_value
    plan_limit = session.exec(
        select(PlanLimit).where(PlanLimit.plan_id == plan_id, PlanLimit.limit_code == limit_code)
    ).first()
    return plan_limit.limit_value if plan_limit else None


def _effective_feature_under_plan(session: Session, tenant_id: uuid.UUID, plan_id: uuid.UUID, feature: Feature) -> bool:
    override = session.exec(
        select(TenantFeatureOverride).where(
            TenantFeatureOverride.tenant_id == tenant_id, TenantFeatureOverride.feature_id == feature.id
        )
    ).first()
    if override is not None:
        return override.enabled
    plan_feature = session.exec(
        select(PlanFeature).where(PlanFeature.plan_id == plan_id, PlanFeature.feature_id == feature.id)
    ).first()
    return plan_feature is not None and plan_feature.enabled


def assess_plan_change_impact(session: Session, tenant: Tenant, target_plan: Plan) -> dict:
    current_plan = session.get(Plan, tenant.active_plan_id) if tenant.active_plan_id else None
    is_downgrade = current_plan is not None and target_plan.setup_price < current_plan.setup_price

    exceeded_limits = []
    for limit_code in PLAN_LIMITS:
        new_limit = _effective_limit_under_plan(session, tenant.id, target_plan.id, limit_code)
        if new_limit is None:
            continue
        current_usage = get_usage(session, tenant.id, limit_code)
        if current_usage > new_limit:
            exceeded_limits.append({"limit_code": limit_code, "current_usage": current_usage, "new_limit": new_limit})

    lost_features = []
    for feature in session.exec(select(Feature)).all():
        if not can_use_feature(session, tenant.id, feature.code):
            continue
        if not _effective_feature_under_plan(session, tenant.id, target_plan.id, feature):
            lost_features.append({"code": feature.code, "name": feature.name})

    return {
        "target_plan_code": target_plan.code,
        "is_downgrade": is_downgrade,
        "exceeded_limits": exceeded_limits,
        "lost_features": lost_features,
    }
