"""Stage 10 — CLAUDE.md's Upgrade Comparison Screen: GET .../plan-comparison
and the upgrade-request create/list endpoints. Requesting an upgrade must
never change the tenant's plan directly."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from tests.test_products import auth_headers
from tests.test_usage_limits import _bootstrap_admin, _tenant_on_plan


def test_plan_comparison_marks_current_and_recommended_plan(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "COMPARE-BASIC")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    resp = client.get("/tenant/me/plan-comparison", headers=headers)
    assert resp.status_code == 200
    body = resp.json()

    plans_by_code = {p["code"]: p for p in body["plans"]}
    assert set(plans_by_code) == {"BASIC", "ESSENTIAL", "ENTERPRISE"}
    assert plans_by_code["BASIC"]["is_current"] is True
    assert plans_by_code["ESSENTIAL"]["is_current"] is False
    assert plans_by_code["ESSENTIAL"]["is_recommended"] is True
    assert plans_by_code["BASIC"]["is_recommended"] is False
    assert plans_by_code["BASIC"]["setup_price"] == "250000.00"
    assert plans_by_code["ESSENTIAL"]["setup_price"] == "350000.00"
    assert plans_by_code["ENTERPRISE"]["setup_price"] == "500000.00"

    barcode_row = next(f for f in body["features"] if f["code"] == "BARCODE_GENERATION")
    assert barcode_row["enabled_by_plan"] == {"BASIC": False, "ESSENTIAL": True, "ENTERPRISE": True}


def test_upgrade_request_does_not_change_plan(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "UPGRADE-REQUEST")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    resp = client.post(
        "/tenant/me/upgrade-requests",
        json={"requested_plan_code": "ENTERPRISE", "note": "need barcode + transfers"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["requested_plan_code"] == "ENTERPRISE"
    assert body["status"] == "pending"

    # the tenant's actual plan/entitlements are unchanged by the request
    entitlements = client.get("/tenant/me/entitlements", headers=headers).json()
    assert entitlements["plan_code"] == "BASIC"
    assert entitlements["features"]["INTER_WAREHOUSE_TRANSFER"] is False


def test_upgrade_request_rejects_current_plan(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "UPGRADE-SAME-PLAN")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    resp = client.post(
        "/tenant/me/upgrade-requests", json={"requested_plan_code": "BASIC"}, headers=headers
    )
    assert resp.status_code == 409


def test_upgrade_request_rejects_unknown_plan(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "UPGRADE-UNKNOWN-PLAN")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    resp = client.post(
        "/tenant/me/upgrade-requests", json={"requested_plan_code": "PLATINUM"}, headers=headers
    )
    assert resp.status_code == 404


def test_sales_role_cannot_request_upgrade(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "UPGRADE-RBAC")
    _bootstrap_admin(session, tenant)
    from app.auth.security import hash_password
    from app.models.user import User, UserRole

    sales = User(tenant_id=tenant.id, username="sales1", password_hash=hash_password("salespass"), role=UserRole.sales)
    session.add(sales)
    session.commit()

    headers = auth_headers(client, "sales1", "salespass", tenant.tenant_code)
    resp = client.post(
        "/tenant/me/upgrade-requests", json={"requested_plan_code": "ESSENTIAL"}, headers=headers
    )
    assert resp.status_code == 403


def test_list_upgrade_requests_scoped_to_tenant(client: TestClient, session: Session):
    tenant_a = _tenant_on_plan(session, "BASIC", "UPGRADE-LIST-A")
    _bootstrap_admin(session, tenant_a)
    tenant_b = _tenant_on_plan(session, "BASIC", "UPGRADE-LIST-B")
    from app.auth.security import hash_password
    from app.models.user import User, UserRole

    admin_b = User(tenant_id=tenant_b.id, username="admin1", password_hash=hash_password("otherpass"), role=UserRole.admin)
    session.add(admin_b)
    session.commit()

    headers_a = auth_headers(client, "admin1", "adminpass", tenant_a.tenant_code)
    headers_b = auth_headers(client, "admin1", "otherpass", tenant_b.tenant_code)

    client.post("/tenant/me/upgrade-requests", json={"requested_plan_code": "ESSENTIAL"}, headers=headers_a)
    client.post("/tenant/me/upgrade-requests", json={"requested_plan_code": "ENTERPRISE"}, headers=headers_b)

    resp = client.get("/tenant/me/upgrade-requests", headers=headers_a)
    assert resp.status_code == 200
    requests = resp.json()
    assert len(requests) == 1
    assert requests[0]["requested_plan_code"] == "ESSENTIAL"
