"""Stage 13 — CLAUDE.md's downgrade-impact check: "Create a downgrade-impact
check before allowing plan reduction." Preview endpoint + confirm-gated
change-plan."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.usage_limits import increment_usage
from tests.test_platform_admin import _platform_admin, _platform_admin_headers
from tests.test_usage_limits import _bootstrap_admin, _tenant_on_plan


def test_upgrade_shows_no_impact(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "IMPACT-UPGRADE")
    _bootstrap_admin(session, tenant)
    headers = _platform_admin_headers(client)

    resp = client.get(
        f"/platform-admin/tenants/{tenant.id}/plan-change-impact",
        params={"target_plan_code": "ENTERPRISE"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_downgrade"] is False
    assert body["exceeded_limits"] == []
    assert body["lost_features"] == []


def test_downgrade_reports_exceeded_limit_and_lost_feature(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "ENTERPRISE", "IMPACT-DOWNGRADE")
    _bootstrap_admin(session, tenant)
    # 6 users total on an Enterprise tenant (limit 30) — Basic's limit is
    # exactly 5, so this tenant would be over Basic's cap on downgrade.
    increment_usage(session, tenant.id, "MAX_USERS", by=5)
    headers = _platform_admin_headers(client)

    resp = client.get(
        f"/platform-admin/tenants/{tenant.id}/plan-change-impact",
        params={"target_plan_code": "BASIC"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_downgrade"] is True

    exceeded = {e["limit_code"]: e for e in body["exceeded_limits"]}
    assert exceeded["MAX_USERS"] == {"limit_code": "MAX_USERS", "current_usage": 6, "new_limit": 5}

    lost_codes = {f["code"] for f in body["lost_features"]}
    assert "BARCODE_GENERATION" in lost_codes  # Enterprise has it, Basic doesn't
    assert "INTER_WAREHOUSE_TRANSFER" in lost_codes  # Enterprise-only


def test_change_plan_blocked_without_confirm_when_impact_exists(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "ENTERPRISE", "IMPACT-BLOCKED")
    _bootstrap_admin(session, tenant)
    headers = _platform_admin_headers(client)

    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/change-plan",
        json={"plan_code": "BASIC", "reason": "customer downgrading"},
        headers=headers,
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "PLAN_CHANGE_IMPACT_REQUIRES_CONFIRMATION"
    assert "BARCODE_GENERATION" in {f["code"] for f in detail["impact"]["lost_features"]}

    # plan is unchanged after the refused attempt
    tenant_detail = client.get(f"/platform-admin/tenants/{tenant.id}", headers=headers).json()
    assert tenant_detail["plan_code"] == "ENTERPRISE"


def test_change_plan_succeeds_with_confirm_and_records_impact_in_audit(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "ENTERPRISE", "IMPACT-CONFIRMED")
    _bootstrap_admin(session, tenant)
    headers = _platform_admin_headers(client)

    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/change-plan",
        json={"plan_code": "BASIC", "reason": "customer downgrading", "confirm": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plan_code"] == "BASIC"

    audit = client.get(f"/platform-admin/tenants/{tenant.id}/audit-log", headers=headers).json()
    entry = next(e for e in audit if e["action"] == "CHANGE_PLAN")
    assert "confirmed_impact" in entry["new_value"]
    assert "BARCODE_GENERATION" in {f["code"] for f in entry["new_value"]["confirmed_impact"]["lost_features"]}


def test_downgrade_preserves_existing_users_and_products(client: TestClient, session: Session):
    """CLAUDE.md: downgrading must never delete data — only block *new*
    creation past the lower cap."""
    from tests.test_products import auth_headers, create_product

    _platform_admin(session)
    tenant = _tenant_on_plan(session, "ENTERPRISE", "IMPACT-PRESERVE-DATA")
    _bootstrap_admin(session, tenant)
    tenant_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    for i in range(2, 7):
        client.post(
            "/users", json={"username": f"user{i}", "password": "pw12345", "role": "sales"}, headers=tenant_headers
        )
    for i in range(6):
        create_product(client, tenant_headers, sku=f"PRESERVE-{i}")

    admin_headers = _platform_admin_headers(client)
    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/change-plan",
        json={"plan_code": "BASIC", "reason": "downgrade", "confirm": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["plan_code"] == "BASIC"
    assert len(detail["users"]) == 6  # all 6 users still exist, none deleted
    assert all(u.get("is_active", True) for u in detail["users"])

    # a new user push past Basic's cap of 5 is blocked, but nothing existing was touched
    resp = client.post(
        "/users", json={"username": "user7", "password": "pw12345", "role": "sales"}, headers=tenant_headers
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "PLAN_LIMIT_REACHED"


def test_upgrade_preserves_all_tenant_data_unchanged(client: TestClient, session: Session):
    from tests.test_products import auth_headers, create_product

    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "IMPACT-PRESERVE-UPGRADE")
    _bootstrap_admin(session, tenant)
    tenant_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    product = create_product(client, tenant_headers, sku="UPGRADE-PRESERVE")

    admin_headers = _platform_admin_headers(client)
    resp = client.post(
        f"/platform-admin/tenants/{tenant.id}/change-plan",
        json={"plan_code": "ENTERPRISE", "reason": "upgrade"},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    # the product created before the upgrade is byte-for-byte unchanged
    after = client.get(f"/products/{product['id']}", headers=tenant_headers).json()
    assert after["sku"] == product["sku"]
    assert after["name"] == product["name"]
    assert after["cost_price"] == product["cost_price"]


def test_plan_change_impact_unknown_plan_404(client: TestClient, session: Session):
    _platform_admin(session)
    tenant = _tenant_on_plan(session, "BASIC", "IMPACT-UNKNOWN-PLAN")
    headers = _platform_admin_headers(client)

    resp = client.get(
        f"/platform-admin/tenants/{tenant.id}/plan-change-impact",
        params={"target_plan_code": "PLATINUM"},
        headers=headers,
    )
    assert resp.status_code == 404
