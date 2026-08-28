"""Feature entitlement resolution — CLAUDE.md Section 11.3. This is the ONLY
place that decides whether a tenant can use a feature. Never write
`if tenant.plan == "ESSENTIAL"` anywhere else in the app; call
`can_use_feature()` or depend on `require_feature()` instead.

Resolution order for a given (tenant, feature):
  1. TenantFeatureOverride for that tenant+feature, if one exists — its
     `enabled` wins outright, in either direction (grants or revokes).
  2. Otherwise, PlanFeature.enabled for the tenant's active plan.
  3. Otherwise False — an unknown feature code, a tenant with no active
     plan, or a plan that never enabled it all fail closed.
"""

import uuid

from fastapi import Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.db import get_session
from app.models.entitlement import TenantFeatureOverride
from app.models.plan import Feature, Plan, PlanFeature
from app.models.tenant import Tenant
from app.models.user import User


def _get_feature(session: Session, feature_code: str) -> Feature | None:
    return session.exec(select(Feature).where(Feature.code == feature_code)).first()


def can_use_feature(session: Session, tenant_id: uuid.UUID, feature_code: str) -> bool:
    feature = _get_feature(session, feature_code)
    if feature is None:
        return False

    override = session.exec(
        select(TenantFeatureOverride).where(
            TenantFeatureOverride.tenant_id == tenant_id,
            TenantFeatureOverride.feature_id == feature.id,
        )
    ).first()
    if override is not None:
        return override.enabled

    tenant = session.get(Tenant, tenant_id)
    if tenant is None or tenant.active_plan_id is None:
        return False

    plan_feature = session.exec(
        select(PlanFeature).where(
            PlanFeature.plan_id == tenant.active_plan_id,
            PlanFeature.feature_id == feature.id,
        )
    ).first()
    return plan_feature is not None and plan_feature.enabled


def _plans_enabling(session: Session, feature_id: uuid.UUID) -> list[Plan]:
    """Every plan that enables this feature by default, cheapest first.
    Overrides are per-tenant and irrelevant to "which plan should I sell
    this customer" messaging, so this only looks at PlanFeature."""
    return list(
        session.exec(
            select(Plan)
            .join(PlanFeature, PlanFeature.plan_id == Plan.id)
            .where(PlanFeature.feature_id == feature_id, PlanFeature.enabled == True)  # noqa: E712
            .order_by(Plan.setup_price)
        )
    )


def _not_available_message(feature_name: str, plans: list[Plan]) -> str:
    if not plans:
        return f"{feature_name} is not available on any current plan."
    names = [p.name for p in plans]
    if len(names) == 1:
        return f"{feature_name} is available in the {names[0]} plan."
    if len(names) == 2:
        return f"{feature_name} is available in {names[0]} and {names[1]} plans."
    return f"{feature_name} is available in {', '.join(names[:-1])}, and {names[-1]} plans."


def describe_feature(session: Session, feature_code: str) -> dict:
    """Plan-static info about a feature — name, cheapest plan that enables
    it, and the human message — independent of any particular tenant.
    Shared by `feature_not_available_error` (the backend 403) and
    `GET /tenant/me/entitlements` (Stage 6 — so the frontend's locked-
    feature card can show the same "available in Essential and Enterprise
    plans" text without re-deriving it from the plan/feature tables
    itself)."""
    feature = _get_feature(session, feature_code)
    feature_name = feature.name if feature else feature_code
    plans = _plans_enabling(session, feature.id) if feature else []
    return {
        "name": feature_name,
        "module": feature.module if feature else "unknown",
        "required_plan": plans[0].code if plans else None,
        "message": _not_available_message(feature_name, plans),
    }


def feature_not_available_error(session: Session, feature_code: str) -> HTTPException:
    """Build the structured 403 for a denied feature gate. Exposed
    separately from `require_feature` so callers that check
    `can_use_feature()` inline (rather than via the FastAPI dependency) can
    raise the exact same error shape."""
    info = describe_feature(session, feature_code)
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "FEATURE_NOT_AVAILABLE",
            "feature": feature_code,
            "required_plan": info["required_plan"],
            "message": info["message"],
        },
    )


def require_feature(feature_code: str):
    """FastAPI dependency factory: `Depends(require_feature("BARCODE_GENERATION"))`.
    Raises the structured 403 above if the current user's tenant can't use
    the feature; otherwise resolves to None and lets the request proceed.
    """

    def dependency(
        session: Session = Depends(get_session),
        user: User = Depends(get_current_user),
    ) -> None:
        if not can_use_feature(session, user.tenant_id, feature_code):
            raise feature_not_available_error(session, feature_code)

    return dependency
