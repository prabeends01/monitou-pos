"""Stage 6 — GET /tenant/me/entitlements: the single snapshot the frontend's
useFeature/FeatureGate (Stage 6) fetches once per session instead of
re-deriving plan logic client-side."""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.plan import Plan
from app.services.subscriptions import ensure_subscription
from tests.test_products import auth_headers
from tests.test_usage_limits import _bootstrap_admin, _tenant_on_plan


def test_entitlements_reflects_basic_plan(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "ENTITLEMENTS-BASIC")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    resp = client.get("/tenant/me/entitlements", headers=headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["tenant_code"] == "ENTITLEMENTS-BASIC"
    assert body["plan_code"] == "BASIC"
    assert body["tenant_status"] == "active"
    assert body["features"]["PRODUCT_MASTER"] is True
    assert body["features"]["BARCODE_GENERATION"] is False
    assert body["features"]["INTER_WAREHOUSE_TRANSFER"] is False
    assert body["limits"]["MAX_USERS"] == {"used": 1, "max": 5}
    assert body["limits"]["MAX_SKUS"] == {"used": 0, "max": 5000}

    barcode_info = body["feature_info"]["BARCODE_GENERATION"]
    assert barcode_info["required_plan"] == "ESSENTIAL"
    assert barcode_info["message"] == "Barcode Generation is available in Essential and Enterprise plans."
    assert barcode_info["module"] == "barcode"

    assert body["subscription"] is None  # _tenant_on_plan never creates one


def test_entitlements_reflects_enterprise_plan(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "ENTERPRISE", "ENTITLEMENTS-ENTERPRISE")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    resp = client.get("/tenant/me/entitlements", headers=headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["plan_code"] == "ENTERPRISE"
    assert body["features"]["BARCODE_GENERATION"] is True
    assert body["features"]["INTER_WAREHOUSE_TRANSFER"] is True
    assert body["limits"]["MAX_USERS"]["max"] == 30


def test_entitlements_requires_auth(client: TestClient):
    resp = client.get("/tenant/me/entitlements")
    assert resp.status_code == 401


def test_entitlements_includes_subscription_when_present(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "ENTITLEMENTS-SUBSCRIPTION")
    _bootstrap_admin(session, tenant)
    plan = session.exec(select(Plan).where(Plan.code == "BASIC")).one()
    ensure_subscription(session, tenant, plan)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    resp = client.get("/tenant/me/entitlements", headers=headers)
    assert resp.status_code == 200
    subscription = resp.json()["subscription"]

    assert subscription["status"] == "ACTIVE"
    assert subscription["setup_fee"] == "250000.00"
    assert subscription["annual_amc"] == "60000.00"
    assert subscription["start_date"] is not None
    assert subscription["renewal_date"] is not None
