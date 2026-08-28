"""Stage 11 — CLAUDE.md Section 11.13: Platform Super Admin. Entirely
separate credential space from tenant users; every mutating action must be
audited with who/when/old/new/reason."""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.security import hash_password
from app.models.plan import Plan
from app.models.platform_admin import PlatformAdmin
from app.models.user import User, UserRole
from tests.test_products import auth_headers
from tests.test_usage_limits import _bootstrap_admin, _tenant_on_plan


def _platform_admin(session: Session, username: str = "platform-admin", password: str = "platformpass") -> PlatformAdmin:
    admin = PlatformAdmin(username=username, password_hash=hash_password(password))
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


def _platform_admin_headers(client: TestClient, username: str = "platform-admin", password: str = "platformpass") -> dict:
    resp = client.post("/platform-admin/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_platform_admin_login_success(client: TestClient, session: Session):
    _platform_admin(session)
    resp = client.post("/platform-admin/auth/login", data={"username": "platform-admin", "password": "platformpass"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_platform_admin_login_wrong_password(client: TestClient, session: Session):
    _platform_admin(session)
    resp = client.post("/platform-admin/auth/login", data={"username": "platform-admin", "password": "wrong"})
    assert resp.status_code == 401


def test_tenant_user_token_rejected_on_platform_admin_route(client: TestClient, admin_user: User):
    tenant_headers = auth_headers(client, "admin1", "adminpass")
    resp = client.get("/platform-admin/dashboard", headers=tenant_headers)
    assert resp.status_code == 401


def test_platform_admin_token_rejected_on_tenant_route(client: TestClient, session: Session):
    admin = _platform_admin(session)
    platform_headers = _platform_admin_headers(client)
    resp = client.get("/users/me", headers=platform_headers)
    assert resp.status_code == 401


def test_dashboard_counts_tenants_by_plan(client: TestClient, session: Session):
    _platform_admin(session)
    _tenant_on_plan(session, "BASIC", "DASH-BASIC")
    _tenant_on_plan(session, "ESSENTIAL", "DASH-ESSENTIAL")
    _tenant_on_plan(session, "ENTERPRISE", "DASH-ENTERPRISE")
    headers = _platform_admin_headers(client)

    resp = client.get("/platform-admin/dashboard", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["basic_customers"] >= 1
    assert body["essential_customers"] >= 1
    assert body["enterprise_customers"] >= 1
    assert body["total_tenants"] >= 3


def test_tenant_list_includes_usage_and_plan(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "LIST-TENANT")
    _bootstrap_admin(session, tenant)
    headers = _platform_admin_headers(client)

    resp = client.get("/platform-admin/tenants", headers=headers)
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["tenant_code"] == "LIST-TENANT")
    assert row["plan_code"] == "BASIC"
    assert row["users_used"] == 1
    assert row["users_max"] == 5
    assert row["tenant_status"] == "active"


def test_tenant_detail_includes_users_and_features(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "DETAIL-TENANT")
    _bootstrap_admin(session, tenant)
    headers = _platform_admin_headers(client)

    resp = client.get(f"/platform-admin/tenants/{tenant.id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan_code"] == "BASIC"
    assert body["features"]["PRODUCT_MASTER"] is True
    assert body["features"]["BARCODE_GENERATION"] is False
    assert [u["username"] for u in body["users"]] == ["admin1"]


def test_change_plan_updates_features_and_writes_audit(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "CHANGE-PLAN-TENANT")
    _bootstrap_admin(session, tenant)
    headers = _platform_admin_headers(client)

    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/change-plan",
        json={"plan_code": "ENTERPRISE", "reason": "customer paid for upgrade"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plan_code"] == "ENTERPRISE"
    assert resp.json()["features"]["BARCODE_GENERATION"] is True

    audit = client.get(f"/platform-admin/tenants/{tenant.id}/audit-log", headers=headers).json()
    entry = next(e for e in audit if e["action"] == "CHANGE_PLAN")
    assert entry["old_value"] == {"plan_code": "BASIC"}
    assert entry["new_value"] == {"plan_code": "ENTERPRISE"}
    assert entry["reason"] == "customer paid for upgrade"
    assert entry["platform_admin_username"] == "platform-admin"


def test_change_plan_approves_matching_pending_upgrade_request(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "APPROVE-REQUEST-TENANT")
    _bootstrap_admin(session, tenant)
    tenant_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    client.post(
        "/tenant/me/upgrade-requests", json={"requested_plan_code": "ESSENTIAL"}, headers=tenant_headers
    )

    admin_headers = _platform_admin_headers(client)
    client.post(
        f"/platform-admin/tenants/{tenant.id}/change-plan",
        json={"plan_code": "ESSENTIAL", "reason": "approved"},
        headers=admin_headers,
    )

    requests = client.get("/tenant/me/upgrade-requests", headers=tenant_headers).json()
    assert requests[0]["status"] == "approved"


def test_feature_override_grants_restricted_feature(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "OVERRIDE-FEATURE-TENANT")
    _bootstrap_admin(session, tenant)
    headers = _platform_admin_headers(client)

    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/feature-overrides",
        json={"feature_code": "BARCODE_GENERATION", "enabled": True, "reason": "bought barcode add-on"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["features"]["BARCODE_GENERATION"] is True
    # plan itself unchanged — only this one tenant's override
    assert resp.json()["plan_code"] == "BASIC"

    audit = client.get(f"/platform-admin/tenants/{tenant.id}/audit-log", headers=headers).json()
    entry = next(e for e in audit if e["action"] == "FEATURE_OVERRIDE")
    assert entry["new_value"] == {"feature_code": "BARCODE_GENERATION", "enabled": True}
    assert entry["reason"] == "bought barcode add-on"


def test_limit_override_raises_capacity(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "OVERRIDE-LIMIT-TENANT")
    _bootstrap_admin(session, tenant)
    headers = _platform_admin_headers(client)

    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/limit-overrides",
        json={"limit_code": "MAX_USERS", "override_value": 8, "reason": "purchased 3 extra seats"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["limits"]["MAX_USERS"]["max"] == 8


def test_suspend_blocks_tenant_login_and_reactivate_restores_it(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "SUSPEND-TENANT")
    _bootstrap_admin(session, tenant)
    headers = _platform_admin_headers(client)

    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/suspend", json={"reason": "AMC unpaid"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["tenant_status"] == "suspended"

    login_resp = client.post(
        "/auth/login", data={"username": "admin1", "password": "adminpass", "client_id": tenant.tenant_code}
    )
    assert login_resp.status_code == 401

    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/reactivate", json={"reason": "AMC paid"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["tenant_status"] == "active"

    login_resp = client.post(
        "/auth/login", data={"username": "admin1", "password": "adminpass", "client_id": tenant.tenant_code}
    )
    assert login_resp.status_code == 200


def test_extend_subscription_updates_renewal_date(client: TestClient, session: Session):
    from app.services.subscriptions import ensure_subscription

    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "EXTEND-SUB-TENANT")
    _bootstrap_admin(session, tenant)
    plan = session.exec(select(Plan).where(Plan.code == "BASIC")).one()
    ensure_subscription(session, tenant, plan)
    headers = _platform_admin_headers(client)

    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/extend-subscription",
        json={"new_renewal_date": "2030-01-01", "reason": "manual extension per support ticket"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["subscription_renewal_date"] == "2030-01-01"

    audit = client.get(f"/platform-admin/tenants/{tenant.id}/audit-log", headers=headers).json()
    entry = next(e for e in audit if e["action"] == "EXTEND_SUBSCRIPTION")
    assert entry["new_value"]["renewal_date"] == "2030-01-01"


def test_missing_reason_is_rejected(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "NO-REASON-TENANT")
    headers = _platform_admin_headers(client)

    resp = client.post(f"/platform-admin/tenants/{tenant.id}/suspend", json={}, headers=headers)
    assert resp.status_code == 422


def test_change_plan_to_unknown_plan_404(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "UNKNOWN-PLAN-TENANT")
    headers = _platform_admin_headers(client)

    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/change-plan",
        json={"plan_code": "PLATINUM", "reason": "x"},
        headers=headers,
    )
    assert resp.status_code == 404


def test_platform_admin_endpoints_require_auth(client: TestClient):
    assert client.get("/platform-admin/dashboard").status_code == 401
    assert client.get("/platform-admin/tenants").status_code == 401
