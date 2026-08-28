"""Usage limit enforcement — CLAUDE.md Section 11.4. This is the ONLY place
that decides whether a tenant has room for one more of something. Never
inline a plan's numeric limit anywhere else; call `check_limit()` before the
create commits, and `increment_usage()`/`decrement_usage()` in the same
service function that creates/deactivates the counted entity.

Resolution order for a given (tenant, limit_code) — mirrors entitlements.py:
  1. TenantLimitOverride for that tenant+limit_code, if one exists.
  2. Otherwise, PlanLimit for the tenant's active plan.

Unlike feature entitlement (which fails closed on an unresolvable feature
code), an unresolvable limit_code is a configuration bug, not a plan
decision — `plan_catalog.py` seeds all four limit codes for every plan, so
this should never actually happen outside of a broken deploy. It raises
`ValueError` rather than silently allowing or denying, so a misconfiguration
surfaces loudly instead of masquerading as either "no limit" or "at limit".
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.entitlement import TenantLimitOverride, UsageCounter
from app.models.plan import Plan, PlanLimit
from app.models.tenant import Tenant

# limit_code -> (plural resource name for the message, singular capacity noun)
_LIMIT_DESCRIPTIONS = {
    "MAX_USERS": ("active users", "user"),
    "MAX_BRANCHES": ("branches", "branch"),
    "MAX_WAREHOUSES": ("warehouses", "warehouse"),
    "MAX_SKUS": ("SKUs", "SKU"),
}


def _resolve_limit_value(session: Session, tenant: Tenant, limit_code: str) -> int:
    override = session.exec(
        select(TenantLimitOverride).where(
            TenantLimitOverride.tenant_id == tenant.id, TenantLimitOverride.limit_code == limit_code
        )
    ).first()
    if override is not None:
        return override.override_value

    if tenant.active_plan_id is None:
        raise ValueError(f"tenant {tenant.id} has no active plan — cannot resolve {limit_code}")

    plan_limit = session.exec(
        select(PlanLimit).where(PlanLimit.plan_id == tenant.active_plan_id, PlanLimit.limit_code == limit_code)
    ).first()
    if plan_limit is None:
        raise ValueError(f"no PlanLimit configured for {limit_code} on plan {tenant.active_plan_id}")
    return plan_limit.limit_value


def get_limit(session: Session, tenant_id: uuid.UUID, limit_code: str) -> int:
    """The resolved numeric limit (override, else plan default) for display
    — e.g. the Plan & Subscription page's "Users: 4 / 5". Raises the same
    `ValueError` as `check_limit` if the tenant/plan/limit can't be
    resolved; callers that only want a best-effort number (like the
    entitlements endpoint, which reports on all four known limit codes
    regardless of whether this tenant's plan has ever been exercised
    against them) should catch it per-limit rather than let one bad code
    take down the whole response."""
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError(f"tenant {tenant_id} does not exist")
    return _resolve_limit_value(session, tenant, limit_code)


def get_usage(session: Session, tenant_id: uuid.UUID, limit_code: str) -> int:
    counter = session.exec(
        select(UsageCounter).where(UsageCounter.tenant_id == tenant_id, UsageCounter.metric_code == limit_code)
    ).first()
    return counter.current_value if counter else 0


def _plan_limit_reached_error(plan_name: str, limit_code: str, limit_value: int, current_value: int) -> HTTPException:
    resource, capacity_noun = _LIMIT_DESCRIPTIONS.get(limit_code, (limit_code, limit_code))
    message = (
        f"Your {plan_name} plan supports up to {limit_value} {resource}. "
        f"Upgrade your plan or purchase additional {capacity_noun} capacity."
    )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "PLAN_LIMIT_REACHED",
            "limit": limit_code,
            "limit_value": limit_value,
            "current_value": current_value,
            "message": message,
        },
    )


def check_limit(session: Session, tenant_id: uuid.UUID, limit_code: str, increment: int = 1) -> None:
    """Raise the structured 409 above if creating `increment` more of
    `limit_code` would exceed the tenant's resolved limit. Call this BEFORE
    the create commits — it does not itself reserve capacity, that's
    `increment_usage()`'s job once the create actually succeeds."""
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise ValueError(f"tenant {tenant_id} does not exist")

    limit_value = _resolve_limit_value(session, tenant, limit_code)
    current_value = get_usage(session, tenant_id, limit_code)
    if current_value + increment > limit_value:
        plan = session.get(Plan, tenant.active_plan_id) if tenant.active_plan_id else None
        raise _plan_limit_reached_error(plan.name if plan else "current", limit_code, limit_value, current_value)


def _get_or_create_counter(session: Session, tenant_id: uuid.UUID, limit_code: str) -> UsageCounter:
    counter = session.exec(
        select(UsageCounter).where(UsageCounter.tenant_id == tenant_id, UsageCounter.metric_code == limit_code)
    ).first()
    if counter is None:
        counter = UsageCounter(tenant_id=tenant_id, metric_code=limit_code, current_value=0)
    return counter


def increment_usage(session: Session, tenant_id: uuid.UUID, limit_code: str, by: int = 1) -> None:
    counter = _get_or_create_counter(session, tenant_id, limit_code)
    counter.current_value += by
    counter.updated_at = datetime.now(timezone.utc)
    session.add(counter)
    session.commit()


def decrement_usage(session: Session, tenant_id: uuid.UUID, limit_code: str, by: int = 1) -> None:
    counter = _get_or_create_counter(session, tenant_id, limit_code)
    counter.current_value = max(0, counter.current_value - by)
    counter.updated_at = datetime.now(timezone.utc)
    session.add(counter)
    session.commit()
