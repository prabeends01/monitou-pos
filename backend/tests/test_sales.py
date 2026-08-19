import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.models.user import User
from tests.test_barcodes import create_barcode
from tests.test_products import auth_headers, create_product


def make_sale_payload(product_id: str, barcode_id: str, qty_base_units: int, unit_price: str = "5.00") -> dict:
    sale_id = str(uuid.uuid4())
    return {
        "id": sale_id,
        "invoice_number": f"T1-{uuid.uuid4().hex[:6]}",
        "invoice_series": "T1",
        "terminal_id": "T1",
        "payment_mode": "cash",
        "gst_amount": "10.00",
        "created_at_client": datetime.now(timezone.utc).isoformat(),
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


def test_sale_of_a_whole_box_decrements_stock_by_pack_qty(client: TestClient, admin_user: User, sales_user: User):
    """Cashier takes the box barcode's default suggestion (the full pack)."""
    admin_headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, admin_headers)
    barcode = create_barcode(client, admin_headers, product["id"], "8900000000028", 100, "Box of 100")
    client.post(
        "/stock/purchases/receive",
        json={"product_id": product["id"], "qty_base_units": 500, "terminal_id": "T1"},
        headers=admin_headers,
    )

    sales_headers = auth_headers(client, "sales1", "salespass")
    payload = make_sale_payload(product["id"], barcode["id"], qty_base_units=200)
    resp = client.post("/sales", json=payload, headers=sales_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["items"][0]["qty_base_units"] == 200
    assert body["total_amount"] == "1000.00"

    balance = client.get(f"/stock/balance/{product['id']}", headers=admin_headers)
    assert balance.json()["balance"] == 300


def test_sale_of_partial_box_uses_edited_qty_not_pack_qty(client: TestClient, admin_user: User, sales_user: User):
    """Cashier scans a box-of-100 barcode but edits the qty down to 25 —
    the box was already open. Server must trust the edited qty_base_units,
    not silently re-multiply by the barcode's pack_qty."""
    admin_headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, admin_headers)
    barcode = create_barcode(client, admin_headers, product["id"], "8900000000028", 100, "Box of 100")
    client.post(
        "/stock/purchases/receive",
        json={"product_id": product["id"], "qty_base_units": 500, "terminal_id": "T1"},
        headers=admin_headers,
    )

    sales_headers = auth_headers(client, "sales1", "salespass")
    payload = make_sale_payload(product["id"], barcode["id"], qty_base_units=25)
    resp = client.post("/sales", json=payload, headers=sales_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["items"][0]["qty_base_units"] == 25
    assert body["total_amount"] == "125.00"

    balance = client.get(f"/stock/balance/{product['id']}", headers=admin_headers)
    assert balance.json()["balance"] == 475


def test_sale_without_invoice_number_gets_one_assigned(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)
    barcode = create_barcode(client, headers, product["id"], "8900000000011", 1, "Single piece")

    payload = make_sale_payload(product["id"], barcode["id"], qty_base_units=1)
    del payload["invoice_number"]
    resp = client.post("/sales", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["invoice_number"] == "T1-1001"


def test_auto_assigned_invoice_numbers_are_sequential(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)
    barcode = create_barcode(client, headers, product["id"], "8900000000011", 1, "Single piece")

    numbers = []
    for _ in range(3):
        payload = make_sale_payload(product["id"], barcode["id"], qty_base_units=1)
        del payload["invoice_number"]
        resp = client.post("/sales", json=payload, headers=headers)
        assert resp.status_code == 201
        numbers.append(resp.json()["invoice_number"])
    assert numbers == ["T1-1001", "T1-1002", "T1-1003"]


def test_sale_rejects_non_positive_qty(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)
    barcode = create_barcode(client, headers, product["id"], "8900000000011", 1, "Single piece")
    payload = make_sale_payload(product["id"], barcode["id"], qty_base_units=0)
    resp = client.post("/sales", json=payload, headers=headers)
    assert resp.status_code == 422


def test_duplicate_sale_id_is_idempotent(client: TestClient, admin_user: User, sales_user: User):
    admin_headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, admin_headers)
    barcode = create_barcode(client, admin_headers, product["id"], "8900000000011", 1, "Single piece")
    client.post(
        "/stock/purchases/receive",
        json={"product_id": product["id"], "qty_base_units": 50, "terminal_id": "T1"},
        headers=admin_headers,
    )

    sales_headers = auth_headers(client, "sales1", "salespass")
    payload = make_sale_payload(product["id"], barcode["id"], qty_base_units=3)

    first = client.post("/sales", json=payload, headers=sales_headers)
    assert first.status_code == 201
    second = client.post("/sales", json=payload, headers=sales_headers)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]

    balance = client.get(f"/stock/balance/{product['id']}", headers=admin_headers)
    assert balance.json()["balance"] == 47, "retried sale must not double-decrement stock"


def test_sales_role_cannot_see_others_sale(client: TestClient, admin_user: User, sales_user: User):
    admin_headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, admin_headers)
    barcode = create_barcode(client, admin_headers, product["id"], "8900000000011", 1, "Single piece")
    client.post(
        "/stock/purchases/receive",
        json={"product_id": product["id"], "qty_base_units": 10, "terminal_id": "T1"},
        headers=admin_headers,
    )

    payload = make_sale_payload(product["id"], barcode["id"], qty_base_units=1)
    admin_sale = client.post("/sales", json=payload, headers=admin_headers)
    assert admin_sale.status_code == 201
    sale_id = admin_sale.json()["id"]

    sales_headers = auth_headers(client, "sales1", "salespass")
    resp = client.get(f"/sales/{sale_id}", headers=sales_headers)
    assert resp.status_code == 403


def test_invoice_pdf_returned(client: TestClient, admin_user: User):
    admin_headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, admin_headers)
    barcode = create_barcode(client, admin_headers, product["id"], "8900000000011", 1, "Single piece")
    client.post(
        "/stock/purchases/receive",
        json={"product_id": product["id"], "qty_base_units": 10, "terminal_id": "T1"},
        headers=admin_headers,
    )

    payload = make_sale_payload(product["id"], barcode["id"], qty_base_units=1)
    sale = client.post("/sales", json=payload, headers=admin_headers)
    sale_id = sale.json()["id"]

    resp = client.get(f"/sales/{sale_id}/invoice", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
