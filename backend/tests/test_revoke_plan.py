"""Platform Admin's revoke-plan action, and the AMC-frozen-at-old-plan bug
it exposed in change_plan (a tenant's displayed AMC never tracked a plan
change — it stayed at whatever it was set to when the subscription row was
first created)."""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.plan import Plan
from app.services.subscriptions import ensure_subscription
from tests.test_platform_admin import _platform_admin, _platform_admin_headers
from tests.test_products import auth_headers
from tests.test_usage_limits import _bootstrap_admin, _tenant_on_plan


def test_change_plan_updates_annual_amc(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "ESSENTIAL", "AMC-UPDATE")
    _bootstrap_admin(session, tenant)
    essential = session.exec(select(Plan).where(Plan.code == "ESSENTIAL")).one()
    ensure_subscription(session, tenant, essential)
    tenant_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    before = client.get("/tenant/me/entitlements", headers=tenant_headers).json()
    assert before["subscription"]["annual_amc"] == "90000.00"

    admin_headers = _platform_admin_headers(client)
    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/change-plan",
        json={"plan_code": "ENTERPRISE", "reason": "upgrade"},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    after = client.get("/tenant/me/entitlements", headers=tenant_headers).json()
    assert after["subscription"]["annual_amc"] == "150000.00"
    assert after["subscription"]["setup_fee"] == "350000.00"  # one-time — untouched by the plan change


def test_revoke_plan_clears_active_plan(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "ESSENTIAL", "REVOKE-BASIC")
    _bootstrap_admin(session, tenant)
    admin_headers = _platform_admin_headers(client)

    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/revoke-plan",
        json={"reason": "non-payment"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plan_code"] is None
    assert resp.json()["plan_name"] is None
    assert all(v is False for v in resp.json()["features"].values())

    audit = client.get(f"/platform-admin/tenants/{tenant.id}/audit-log", headers=admin_headers).json()
    entry = next(e for e in audit if e["action"] == "REVOKE_PLAN")
    assert entry["old_value"] == {"plan_code": "ESSENTIAL"}
    assert entry["new_value"] == {"plan_code": None}
    assert entry["reason"] == "non-payment"


def test_revoked_tenant_can_still_log_in_but_loses_all_features(client: TestClient, session: Session):
    """Revoke is not suspend — the account itself stays reachable, but the
    plan-gated capabilities are gone."""
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "ESSENTIAL", "REVOKE-STILL-LOGIN")
    _bootstrap_admin(session, tenant)
    admin_headers = _platform_admin_headers(client)
    client.post(f"/platform-admin/tenants/{tenant.id}/revoke-plan", json={"reason": "x"}, headers=admin_headers)

    tenant_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    resp = client.get("/products", headers=tenant_headers)
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "FEATURE_NOT_AVAILABLE"


def test_revoked_tenant_user_create_fails_clean_not_500(client: TestClient, session: Session):
    """POST /users has no require_feature gate (base user management isn't
    a catalog feature), so it's the one place check_limit's NO_ACTIVE_PLAN
    handling is actually exercised — this used to raise a bare unhandled
    ValueError (500) once a tenant had no active plan."""
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "ESSENTIAL", "REVOKE-USER-CREATE")
    _bootstrap_admin(session, tenant)
    admin_headers = _platform_admin_headers(client)
    client.post(f"/platform-admin/tenants/{tenant.id}/revoke-plan", json={"reason": "x"}, headers=admin_headers)

    tenant_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    resp = client.post(
        "/users", json={"username": "user2", "password": "pw12345", "role": "sales"}, headers=tenant_headers
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "NO_ACTIVE_PLAN"


def test_revoke_plan_twice_conflicts(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "REVOKE-TWICE")
    admin_headers = _platform_admin_headers(client)
    client.post(f"/platform-admin/tenants/{tenant.id}/revoke-plan", json={"reason": "x"}, headers=admin_headers)
    resp = client.post(f"/platform-admin/tenants/{tenant.id}/revoke-plan", json={"reason": "x"}, headers=admin_headers)
    assert resp.status_code == 409
