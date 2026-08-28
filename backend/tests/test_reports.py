import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.user import User
from app.services.reports import low_stock_products
from tests.test_barcodes import create_barcode
from tests.test_products import auth_headers, create_product


def sale_payload(product_id: str, barcode_id: str, qty_base_units: int, unit_price: str, when: datetime) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "invoice_number": f"T1-{uuid.uuid4().hex[:6]}",
        "invoice_series": "T1",
        "terminal_id": "T1",
        "payment_mode": "cash",
        "gst_amount": "9.00",
        "created_at_client": when.isoformat(),
        "items": [
            {
                "id": str(uuid.uuid4()),
                "product_id": product_id,
                "barcode_id": barcode_id,
                "qty_base_units": qty_base_units,
                "unit_price": unit_price,
            }
        ],
    }


def test_sales_summary_bucket_totals_match_fixture(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)
    barcode = create_barcode(client, headers, product["id"], "8900000000011", 1, "Single piece")
    client.post(
        "/stock/purchases/receive",
        json={"product_id": product["id"], "qty_base_units": 1000, "terminal_id": "T1"},
        headers=headers,
    )

    day = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    # two sales same day: 2*5.00 + 3*5.00 = 25.00 total, gst 9+9=18
    for qty in (2, 3):
        resp = client.post("/sales", json=sale_payload(product["id"], barcode["id"], qty, "5.00", day), headers=headers)
        assert resp.status_code == 201, resp.text

    resp = client.get(
        "/reports/sales-summary",
        params={"period": "daily", "from": "2026-01-01T00:00:00Z", "to": "2026-01-31T00:00:00Z"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    buckets = resp.json()
    assert len(buckets) == 1
    bucket = buckets[0]
    assert bucket["invoice_count"] == 2
    assert Decimal(bucket["total_sales"]) == Decimal("25.00")
    assert Decimal(bucket["total_gst"]) == Decimal("18.00")
    assert bucket["top_products"][0]["qty_sold"] == 5


def test_sales_summary_rejects_sales_role(client: TestClient, admin_user: User, sales_user: User):
    headers = auth_headers(client, "sales1", "salespass")
    resp = client.get(
        "/reports/sales-summary",
        params={"period": "daily", "from": "2026-01-01T00:00:00Z", "to": "2026-01-31T00:00:00Z"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_stock_stats_rejects_sales_role(client: TestClient, admin_user: User, sales_user: User):
    headers = auth_headers(client, "sales1", "salespass")
    resp = client.get("/reports/stock-stats", headers=headers)
    assert resp.status_code == 403


def test_stock_stats_admin_sees_totals(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)
    client.post(
        "/stock/purchases/receive",
        json={"product_id": product["id"], "qty_base_units": 100, "terminal_id": "T1"},
        headers=headers,
    )
    resp = client.get("/reports/stock-stats", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_skus"] == 1
    assert Decimal(body["total_stock_value"]) == Decimal("350.00")  # 100 units * 3.50 cost_price


def test_low_stock_alerts_endpoint_matches_shared_query(client: TestClient, admin_user: User, session: Session):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)  # reorder_threshold=200, no stock received yet

    resp = client.get("/reports/low-stock-alerts", headers=headers)
    assert resp.status_code == 200
    endpoint_skus = {a["sku"] for a in resp.json()}

    direct_result = low_stock_products(session, tenant_id=admin_user.tenant_id)
    direct_skus = {a.sku for a in direct_result}

    assert endpoint_skus == direct_skus == {product["sku"]}


def test_low_stock_alerts_rejects_sales_role(client: TestClient, admin_user: User, sales_user: User):
    headers = auth_headers(client, "sales1", "salespass")
    resp = client.get("/reports/low-stock-alerts", headers=headers)
    assert resp.status_code == 403
