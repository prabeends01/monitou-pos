"""Subscription status lifecycle — CLAUDE.md Section 11.8/PLAN EXPIRY
section: "Do not immediately destroy access on expiry... configurable
grace period... During expired/grace status, show clear notifications...
Platform Admin controls final suspension policy."

Timeline for a subscription with `renewal_date` R, window `W`
(`subscription_expiring_window_days`) and grace `G`
(`subscription_grace_period_days`):

    ACTIVE  |  EXPIRING  |  EXPIRED  |  GRACE_PERIOD  |  SUSPENDED
    ........|............|...........|................|...........>
        R-W            R          R (same day)      R+G

`resolve_subscription_status` is pure — no DB, no side effects — so it's
directly unit-testable against any (renewal_date, today) pair without a
session or a scheduled job. `sync_subscription_status` is the only thing
that persists it, and only ever *advances* a tenant that is still
`TenantStatus.active`: once a tenant is suspended (by this reaching the
final SUSPENDED cutoff, or by a platform admin suspending it directly for
an unrelated reason), this module leaves it alone — reactivating is always
an explicit Platform Admin action (`reactivate`/`extend-subscription`),
never something date math does on its own.
"""

from datetime import date, timedelta

from sqlmodel import Session

from app.config import settings
from app.models.tenant import Subscription, SubscriptionStatus, Tenant, TenantStatus
from app.services.subscriptions import get_current_subscription


def resolve_subscription_status(
    renewal_date: date | None,
    today: date,
    expiring_window_days: int,
    grace_period_days: int,
) -> SubscriptionStatus:
    if renewal_date is None:
        return SubscriptionStatus.active

    expiring_start = renewal_date - timedelta(days=expiring_window_days)
    grace_end = renewal_date + timedelta(days=grace_period_days)

    if today < expiring_start:
        return SubscriptionStatus.active
    if today < renewal_date:
        return SubscriptionStatus.expiring
    if today == renewal_date:
        return SubscriptionStatus.expired
    if today <= grace_end:
        return SubscriptionStatus.grace_period
    return SubscriptionStatus.suspended


def sync_subscription_status(session: Session, tenant: Tenant, today: date | None = None) -> Subscription | None:
    """Recomputes and persists `tenant`'s current subscription's status if
    it's drifted from what the dates say it should be. No-op if the tenant
    has no subscription, or is already suspended (see module docstring)."""
    if tenant.status != TenantStatus.active:
        return get_current_subscription(session, tenant.id)

    subscription = get_current_subscription(session, tenant.id)
    if subscription is None:
        return None

    resolved = resolve_subscription_status(
        subscription.renewal_date,
        today or date.today(),
        settings.subscription_expiring_window_days,
        settings.subscription_grace_period_days,
    )
    if resolved == subscription.status:
        return subscription

    subscription.status = resolved
    session.add(subscription)
    if resolved == SubscriptionStatus.suspended:
        tenant.status = TenantStatus.suspended
        session.add(tenant)
    session.commit()
    session.refresh(subscription)
    return subscription
