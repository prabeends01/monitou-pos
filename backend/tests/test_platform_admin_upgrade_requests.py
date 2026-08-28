"""Platform Admin's cross-tenant upgrade-request inbox — closes the gap
where a request only ever surfaced if an admin happened to open that exact
tenant and change its plan themselves."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from tests.test_platform_admin import _platform_admin, _platform_admin_headers
from tests.test_products import auth_headers
from tests.test_usage_limits import _bootstrap_admin, _tenant_on_plan


def test_dashboard_counts_pending_upgrade_requests(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "UR-DASHBOARD")
    _bootstrap_admin(session, tenant)
    tenant_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    client.post("/tenant/me/upgrade-requests", json={"requested_plan_code": "ESSENTIAL"}, headers=tenant_headers)

    admin_headers = _platform_admin_headers(client)
    resp = client.get("/platform-admin/dashboard", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["pending_upgrade_requests"] >= 1


def test_list_upgrade_requests_shows_pending_across_tenants(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "UR-LIST")
    _bootstrap_admin(session, tenant)
    tenant_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    client.post(
        "/tenant/me/upgrade-requests",
        json={"requested_plan_code": "ESSENTIAL", "note": "need barcode printing"},
        headers=tenant_headers,
    )

    admin_headers = _platform_admin_headers(client)
    resp = client.get("/platform-admin/upgrade-requests", headers=admin_headers)
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["tenant_code"] == "UR-LIST")
    assert row["requested_plan_code"] == "ESSENTIAL"
    assert row["company_name"] == "UR-LIST"
    assert row["requested_by_username"] == "admin1"
    assert row["note"] == "need barcode printing"
    assert row["status"] == "pending"


def test_list_upgrade_requests_defaults_to_pending_only(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "UR-FILTER")
    _bootstrap_admin(session, tenant)
    tenant_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    resp = client.post(
        "/tenant/me/upgrade-requests", json={"requested_plan_code": "ESSENTIAL"}, headers=tenant_headers
    )
    request_id = resp.json()["id"]

    admin_headers = _platform_admin_headers(client)
    client.post(
        f"/platform-admin/upgrade-requests/{request_id}/reject",
        json={"reason": "not needed"},
        headers=admin_headers,
    )

    pending_only = client.get("/platform-admin/upgrade-requests", headers=admin_headers).json()
    assert not any(r["tenant_code"] == "UR-FILTER" for r in pending_only)

    with_decided = client.get(
        "/platform-admin/upgrade-requests", params={"include_decided": True}, headers=admin_headers
    ).json()
    row = next(r for r in with_decided if r["tenant_code"] == "UR-FILTER")
    assert row["status"] == "rejected"


def test_approve_upgrade_request_changes_plan(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "UR-APPROVE")
    _bootstrap_admin(session, tenant)
    tenant_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    resp = client.post(
        "/tenant/me/upgrade-requests", json={"requested_plan_code": "ENTERPRISE"}, headers=tenant_headers
    )
    request_id = resp.json()["id"]

    admin_headers = _platform_admin_headers(client)
    resp = client.post(
        f"/platform-admin/upgrade-requests/{request_id}/approve",
        json={"reason": "payment received"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plan_code"] == "ENTERPRISE"

    requests = client.get("/tenant/me/upgrade-requests", headers=tenant_headers).json()
    assert requests[0]["status"] == "approved"

    # gone from the pending inbox now that it's decided
    still_pending = client.get("/platform-admin/upgrade-requests", headers=admin_headers).json()
    assert not any(r["id"] == request_id for r in still_pending)


def test_reject_upgrade_request_does_not_change_plan(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "UR-REJECT")
    _bootstrap_admin(session, tenant)
    tenant_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    resp = client.post(
        "/tenant/me/upgrade-requests", json={"requested_plan_code": "ENTERPRISE"}, headers=tenant_headers
    )
    request_id = resp.json()["id"]

    admin_headers = _platform_admin_headers(client)
    resp = client.post(
        f"/platform-admin/upgrade-requests/{request_id}/reject",
        json={"reason": "not eligible yet"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    entitlements = client.get("/tenant/me/entitlements", headers=tenant_headers).json()
    assert entitlements["plan_code"] == "BASIC"  # unchanged


def test_approve_already_decided_request_conflicts(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "UR-DOUBLE-DECIDE")
    _bootstrap_admin(session, tenant)
    tenant_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    resp = client.post(
        "/tenant/me/upgrade-requests", json={"requested_plan_code": "ESSENTIAL"}, headers=tenant_headers
    )
    request_id = resp.json()["id"]

    admin_headers = _platform_admin_headers(client)
    client.post(
        f"/platform-admin/upgrade-requests/{request_id}/reject", json={"reason": "no"}, headers=admin_headers
    )
    resp = client.post(
        f"/platform-admin/upgrade-requests/{request_id}/approve",
        json={"reason": "changed my mind"},
        headers=admin_headers,
    )
    assert resp.status_code == 409


def test_upgrade_request_endpoints_require_platform_admin(client: TestClient):
    assert client.get("/platform-admin/upgrade-requests").status_code == 401
