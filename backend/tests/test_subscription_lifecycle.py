"""Stage 14 — CLAUDE.md Section 11.8: "Do not immediately destroy access on
expiry... configurable grace period... Platform Admin controls final
suspension policy." Covers the last item in the Section 11.11 test list:
expired-tenant behavior matches the configured grace-period policy at each
status.
"""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.tenant import SubscriptionStatus, TenantStatus
from app.services.subscription_lifecycle import resolve_subscription_status, sync_subscription_status
from app.services.subscriptions import ensure_subscription, get_current_subscription
from tests.test_platform_admin import _platform_admin_headers
from tests.test_products import auth_headers
from tests.test_usage_limits import _bootstrap_admin, _tenant_on_plan

WINDOW = 30
GRACE = 15


def test_resolve_status_active_well_before_renewal():
    renewal = date(2026, 6, 30)
    today = date(2026, 5, 1)  # 60 days out, outside the 30-day window
    assert resolve_subscription_status(renewal, today, WINDOW, GRACE) == SubscriptionStatus.active


def test_resolve_status_expiring_inside_window():
    renewal = date(2026, 6, 30)
    today = date(2026, 6, 15)  # 15 days out, inside the 30-day window
    assert resolve_subscription_status(renewal, today, WINDOW, GRACE) == SubscriptionStatus.expiring


def test_resolve_status_expired_on_renewal_day():
    renewal = date(2026, 6, 30)
    assert resolve_subscription_status(renewal, renewal, WINDOW, GRACE) == SubscriptionStatus.expired


def test_resolve_status_grace_period_after_renewal():
    renewal = date(2026, 6, 30)
    today = renewal + timedelta(days=10)  # within the 15-day grace period
    assert resolve_subscription_status(renewal, today, WINDOW, GRACE) == SubscriptionStatus.grace_period


def test_resolve_status_suspended_after_grace_elapses():
    renewal = date(2026, 6, 30)
    today = renewal + timedelta(days=16)  # one day past the 15-day grace period
    assert resolve_subscription_status(renewal, today, WINDOW, GRACE) == SubscriptionStatus.suspended


def test_resolve_status_active_with_no_renewal_date():
    assert resolve_subscription_status(None, date.today(), WINDOW, GRACE) == SubscriptionStatus.active


def test_sync_advances_status_and_does_not_touch_tenant_before_suspension(session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "LIFECYCLE-EXPIRING")
    from app.models.plan import Plan
    from sqlmodel import select

    plan = session.exec(select(Plan).where(Plan.code == "BASIC")).one()
    subscription = ensure_subscription(session, tenant, plan)
    subscription.renewal_date = date.today() + timedelta(days=10)  # inside the default 30-day window
    session.add(subscription)
    session.commit()

    sync_subscription_status(session, tenant)
    updated = get_current_subscription(session, tenant.id)
    assert updated.status == SubscriptionStatus.expiring
    assert tenant.status == TenantStatus.active  # expiring must not block access


def test_sync_suspends_tenant_once_grace_period_fully_elapses(session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "LIFECYCLE-SUSPEND")
    from app.models.plan import Plan
    from sqlmodel import select

    plan = session.exec(select(Plan).where(Plan.code == "BASIC")).one()
    subscription = ensure_subscription(session, tenant, plan)
    subscription.renewal_date = date.today() - timedelta(days=100)  # long past grace
    session.add(subscription)
    session.commit()

    sync_subscription_status(session, tenant)
    updated = get_current_subscription(session, tenant.id)
    assert updated.status == SubscriptionStatus.suspended
    assert tenant.status == TenantStatus.suspended


def test_sync_does_not_reactivate_an_already_suspended_tenant(session: Session):
    """A manually-suspended tenant (e.g. AMC unpaid, unrelated to dates)
    must not be silently reactivated just because its renewal_date happens
    to still be in the future."""
    tenant = _tenant_on_plan(session, "BASIC", "LIFECYCLE-NO-REACTIVATE")
    from app.models.plan import Plan
    from sqlmodel import select

    plan = session.exec(select(Plan).where(Plan.code == "BASIC")).one()
    subscription = ensure_subscription(session, tenant, plan)
    subscription.renewal_date = date.today() + timedelta(days=200)  # comfortably active by date
    session.add(subscription)
    tenant.status = TenantStatus.suspended
    session.add(tenant)
    session.commit()

    sync_subscription_status(session, tenant)
    assert tenant.status == TenantStatus.suspended  # untouched


def test_expired_tenant_login_blocked_end_to_end(client: TestClient, session: Session):
    """The full path: a login attempt right at the grace-period cutoff is
    rejected, without any platform admin action or scheduled job having
    run first — auth/deps.py's login endpoint syncs status itself."""
    tenant = _tenant_on_plan(session, "BASIC", "LIFECYCLE-LOGIN-BLOCKED")
    _bootstrap_admin(session, tenant)
    from app.models.plan import Plan
    from sqlmodel import select

    plan = session.exec(select(Plan).where(Plan.code == "BASIC")).one()
    subscription = ensure_subscription(session, tenant, plan)
    subscription.renewal_date = date.today() - timedelta(days=1000)
    session.add(subscription)
    session.commit()

    resp = client.post(
        "/auth/login", data={"username": "admin1", "password": "adminpass", "client_id": tenant.tenant_code}
    )
    assert resp.status_code == 401


def test_expiring_tenant_can_still_use_the_app(client: TestClient, session: Session):
    """CLAUDE.md: "Do not immediately destroy access on expiry" — EXPIRING
    and GRACE_PERIOD must not block anything, only the final SUSPENDED
    cutoff does."""
    tenant = _tenant_on_plan(session, "BASIC", "LIFECYCLE-STILL-WORKS")
    _bootstrap_admin(session, tenant)
    from app.models.plan import Plan
    from sqlmodel import select

    plan = session.exec(select(Plan).where(Plan.code == "BASIC")).one()
    subscription = ensure_subscription(session, tenant, plan)
    subscription.renewal_date = date.today() + timedelta(days=5)  # EXPIRING
    session.add(subscription)
    session.commit()

    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    resp = client.get("/tenant/me/entitlements", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["subscription"]["status"] == "EXPIRING"
    assert resp.json()["tenant_status"] == "active"

    # ordinary business actions still work
    resp = client.post(
        "/products",
        json={"sku": "STILL-WORKS", "name": "x", "category": "x", "cost_price": "1", "sale_price": "2"},
        headers=headers,
    )
    assert resp.status_code == 201


def test_extend_subscription_clears_grace_period_and_restores_login(client: TestClient, session: Session):
    from app.models.plan import Plan
    from sqlmodel import select

    from tests.test_platform_admin import _platform_admin

    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "LIFECYCLE-EXTEND-RESTORE")
    _bootstrap_admin(session, tenant)
    plan = session.exec(select(Plan).where(Plan.code == "BASIC")).one()
    subscription = ensure_subscription(session, tenant, plan)
    subscription.renewal_date = date.today() - timedelta(days=1000)
    session.add(subscription)
    session.commit()

    # confirm it's actually blocked first
    assert (
        client.post(
            "/auth/login", data={"username": "admin1", "password": "adminpass", "client_id": tenant.tenant_code}
        ).status_code
        == 401
    )

    admin_headers = _platform_admin_headers(client)
    new_renewal = str(date.today() + timedelta(days=365))
    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/extend-subscription",
        json={"new_renewal_date": new_renewal, "reason": "AMC paid"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["tenant_status"] == "active"

    resp = client.post(
        "/auth/login", data={"username": "admin1", "password": "adminpass", "client_id": tenant.tenant_code}
    )
    assert resp.status_code == 200
