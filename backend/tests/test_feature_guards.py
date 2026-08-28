"""Stage 5 — CLAUDE.md Section 11.6/11.11: `require_feature` actually wired
onto routers, not just implemented as an unused service. Covers the one
gate wired today that's meaningfully different across plans
(BARCODE_GENERATION), and the stock-stats per-field analytics gate.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from tests.test_products import auth_headers
from tests.test_usage_limits import _bootstrap_admin, _tenant_on_plan


def test_basic_tenant_cannot_create_barcode(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "GUARD-BASIC-BARCODE")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    resp = client.post(
        "/products",
        json={"sku": "X-1", "name": "x", "category": "x", "cost_price": "1", "sale_price": "2"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    product_id = resp.json()["id"]

    resp = client.post(
        "/barcodes",
        json={"product_id": product_id, "barcode_value": "8900000000099", "pack_qty": 1, "label": "Single"},
        headers=headers,
    )
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["code"] == "FEATURE_NOT_AVAILABLE"
    assert detail["feature"] == "BARCODE_GENERATION"
    assert detail["required_plan"] == "ESSENTIAL"
    assert detail["message"] == "Barcode Generation is available in Essential and Enterprise plans."


def test_essential_tenant_can_create_barcode(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "ESSENTIAL", "GUARD-ESSENTIAL-BARCODE")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    resp = client.post(
        "/products",
        json={"sku": "X-2", "name": "x", "category": "x", "cost_price": "1", "sale_price": "2"},
        headers=headers,
    )
    product_id = resp.json()["id"]

    resp = client.post(
        "/barcodes",
        json={"product_id": product_id, "barcode_value": "8900000000098", "pack_qty": 1, "label": "Single"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


def test_enterprise_tenant_can_create_barcode(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "ENTERPRISE", "GUARD-ENTERPRISE-BARCODE")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    resp = client.post(
        "/products",
        json={"sku": "X-3", "name": "x", "category": "x", "cost_price": "1", "sale_price": "2"},
        headers=headers,
    )
    product_id = resp.json()["id"]

    resp = client.post(
        "/barcodes",
        json={"product_id": product_id, "barcode_value": "8900000000097", "pack_qty": 1, "label": "Single"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


def _post_bare_sale(client: TestClient, headers: dict, product_id: str) -> None:
    """A sale with no barcode_id — proves stock-stats population doesn't
    depend on BARCODE_GENERATION, which a Basic tenant can't reach."""
    resp = client.post(
        "/sales",
        json={
            "id": str(uuid.uuid4()),
            "invoice_series": "T1",
            "terminal_id": "T1",
            "payment_mode": "cash",
            "gst_amount": "0",
            "created_at_client": datetime.now(timezone.utc).isoformat(),
            "items": [
                {
                    "id": str(uuid.uuid4()),
                    "product_id": product_id,
                    "qty_base_units": 2,
                    "unit_price": "5.00",
                }
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


def test_basic_tenant_stock_stats_hides_movement_analytics(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "GUARD-BASIC-STOCK-STATS")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    product = client.post(
        "/products",
        json={"sku": "MOVER-1", "name": "x", "category": "x", "cost_price": "1", "sale_price": "5"},
        headers=headers,
    ).json()
    client.post(
        "/stock/purchases/receive",
        json={"product_id": product["id"], "qty_base_units": 50, "terminal_id": "T1"},
        headers=headers,
    )
    _post_bare_sale(client, headers, product["id"])

    resp = client.get("/reports/stock-stats", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_skus"] == 1  # Basic-tier fields still populated
    assert body["fastest_moving"] == []  # Essential+ analytics suppressed
    assert body["slowest_moving"] == []


def test_essential_tenant_stock_stats_shows_movement_analytics(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "ESSENTIAL", "GUARD-ESSENTIAL-STOCK-STATS")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    product = client.post(
        "/products",
        json={"sku": "MOVER-2", "name": "x", "category": "x", "cost_price": "1", "sale_price": "5"},
        headers=headers,
    ).json()
    client.post(
        "/stock/purchases/receive",
        json={"product_id": product["id"], "qty_base_units": 50, "terminal_id": "T1"},
        headers=headers,
    )
    _post_bare_sale(client, headers, product["id"])

    resp = client.get("/reports/stock-stats", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["fastest_moving"]) == 1
    assert body["fastest_moving"][0]["sku"] == "MOVER-2"
