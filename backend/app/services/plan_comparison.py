"""Builds the Upgrade Comparison Screen's data (CLAUDE.md Stage 10) —
plan-static feature-by-plan defaults, straight from `PlanFeature`, not
`can_use_feature()`. Deliberately ignores `TenantFeatureOverride`: a
comparison chart answers "what does each plan normally include," not "what
does this one tenant currently have" (that's `GET /tenant/me/entitlements`,
Stage 6) — showing a tenant's paid-addon override here would misrepresent
what they'd actually be buying by switching plans."""

import uuid

from sqlmodel import Session, select

from app.models.plan import Feature, Plan, PlanFeature
from app.models.tenant import Tenant
from app.schemas.plan_comparison import ComparisonFeatureRow, PlanColumn, PlanComparisonResponse

RECOMMENDED_PLAN_CODE = "ESSENTIAL"  # CLAUDE.md Section 11.5 — Essential is the default/recommended package


def build_plan_comparison(session: Session, tenant_id: uuid.UUID) -> PlanComparisonResponse:
    tenant = session.get(Tenant, tenant_id)
    current_plan = session.get(Plan, tenant.active_plan_id) if tenant and tenant.active_plan_id else None

    plans = list(session.exec(select(Plan).order_by(Plan.setup_price)))
    features = list(session.exec(select(Feature).order_by(Feature.module, Feature.name)))
    all_links = list(session.exec(select(PlanFeature).where(PlanFeature.enabled == True)))  # noqa: E712

    enabled_pairs = {(link.plan_id, link.feature_id) for link in all_links}

    plan_columns = [
        PlanColumn(
            code=plan.code,
            name=plan.name,
            setup_price=str(plan.setup_price),
            annual_amc=str(plan.annual_amc),
            is_current=current_plan is not None and plan.id == current_plan.id,
            is_recommended=plan.code == RECOMMENDED_PLAN_CODE,
        )
        for plan in plans
    ]

    feature_rows = [
        ComparisonFeatureRow(
            code=feature.code,
            name=feature.name,
            module=feature.module,
            enabled_by_plan={plan.code: (plan.id, feature.id) in enabled_pairs for plan in plans},
        )
        for feature in features
    ]

    return PlanComparisonResponse(plans=plan_columns, features=feature_rows)
