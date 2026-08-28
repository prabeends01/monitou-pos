"""Subscription lookup/bootstrap — CLAUDE.md Section 11.8. A tenant should
always have exactly one *current* subscription row; this module is the only
place that decides which row that is, and the only place a subscription
gets created for a tenant that doesn't have one yet.

Full lifecycle management (renewal, plan-change history, expiry
transitions) is Stage 13 — this is deliberately just enough to back the
Stage 9 Plan & Subscription page: "what is this tenant's current term."
"""

import uuid
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.plan import Plan
from app.models.tenant import Subscription, SubscriptionStatus, Tenant

DEFAULT_TERM_DAYS = 365


def get_current_subscription(session: Session, tenant_id: uuid.UUID) -> Subscription | None:
    """The tenant's current term — the one with the latest `start_date`.
    Returns None for a tenant with no subscription row at all (predates
    Stage 9, or was created without one) rather than fabricating one; the
    frontend must handle that case explicitly, not assume a subscription
    always exists."""
    return session.exec(
        select(Subscription).where(Subscription.tenant_id == tenant_id).order_by(Subscription.start_date.desc())
    ).first()


def ensure_subscription(session: Session, tenant: Tenant, plan: Plan) -> Subscription:
    """Idempotent bootstrap: create a subscription for `tenant` on `plan` if
    it doesn't already have a current one. Used by seed/demo data setup —
    a real tenant onboarding flow (Stage 11/13) would create this
    explicitly at signup/upgrade time instead of relying on this fallback."""
    existing = get_current_subscription(session, tenant.id)
    if existing is not None:
        return existing

    start = date.today()
    subscription = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        start_date=start,
        end_date=None,
        status=SubscriptionStatus.active,
        setup_fee=plan.setup_price,
        annual_amc=plan.annual_amc,
        renewal_date=start + timedelta(days=DEFAULT_TERM_DAYS),
    )
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return subscription
