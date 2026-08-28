"""One-time backfill: initialize usage_counters from actual row counts for
tenants that predate Stage 4 (their users/products exist, but nothing ever
called `increment_usage()` for them). After this runs once, `check_limit`'s
counters stay accurate incrementally via `increment_usage`/`decrement_usage`
at each create/deactivate call site — this script is not part of that
ongoing path, it only repairs history. Idempotent: safe to run again, it
always sets (not adds to) each counter from a fresh count.

Only reconciles the two metrics with a real create-flow today (MAX_USERS,
MAX_SKUS) — see CLAUDE.md Section 11.1: branches/warehouses have no backing
module yet, so their counters stay at 0 until those modules exist.

Run: uv run python -m app.reconcile_usage_counters
"""

from datetime import datetime, timezone

from sqlmodel import Session, func, select

from app.db import engine
from app.models.entitlement import UsageCounter
from app.models.product import Product
from app.models.tenant import Tenant
from app.models.user import User


def _set_counter(session: Session, tenant_id, metric_code: str, value: int) -> None:
    counter = session.exec(
        select(UsageCounter).where(UsageCounter.tenant_id == tenant_id, UsageCounter.metric_code == metric_code)
    ).first()
    if counter is None:
        counter = UsageCounter(tenant_id=tenant_id, metric_code=metric_code, current_value=value)
    else:
        counter.current_value = value
    counter.updated_at = datetime.now(timezone.utc)
    session.add(counter)


def reconcile_usage_counters(session: Session) -> None:
    tenants = session.exec(select(Tenant)).all()
    for tenant in tenants:
        active_users = session.exec(
            select(func.count()).select_from(User).where(User.tenant_id == tenant.id, User.is_active == True)  # noqa: E712
        ).one()
        _set_counter(session, tenant.id, "MAX_USERS", active_users)

        total_skus = session.exec(select(func.count()).select_from(Product).where(Product.tenant_id == tenant.id)).one()
        _set_counter(session, tenant.id, "MAX_SKUS", total_skus)

    session.commit()
    print(f"reconciled usage_counters (MAX_USERS, MAX_SKUS) for {len(tenants)} tenant(s)")


if __name__ == "__main__":
    with Session(engine) as _session:
        reconcile_usage_counters(_session)
