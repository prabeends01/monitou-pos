import uuid

from fastapi.testclient import TestClient

from app.models.user import User
from tests.test_products import auth_headers, create_product


def test_purchase_receive_increases_balance(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)

    resp = client.post(
        "/stock/purchases/receive",
        json={"product_id": product["id"], "qty_base_units": 300, "terminal_id": "T1"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["balance_after"] == 300
    assert body["went_negative"] is False


def test_duplicate_movement_id_is_idempotent(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)
    movement_id = str(uuid.uuid4())

    payload = {
        "id": movement_id,
        "product_id": product["id"],
        "qty_base_units": 50,
        "terminal_id": "T1",
    }
    first = client.post("/stock/purchases/receive", json=payload, headers=headers)
    assert first.status_code == 201
    assert first.json()["balance_after"] == 50

    second = client.post("/stock/purchases/receive", json=payload, headers=headers)
    assert second.status_code == 201
    assert second.json()["balance_after"] == 50, "duplicate ID must not double-count"

    balance = client.get(f"/stock/balance/{product['id']}", headers=headers)
    assert balance.json()["balance"] == 50


def test_adjustment_going_negative_is_flagged(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)

    resp = client.post(
        "/stock/adjustments",
        json={"product_id": product["id"], "qty_base_units": -5, "terminal_id": "T1"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["balance_after"] == -5
    assert body["went_negative"] is True


def test_purchase_receive_rejects_non_positive_qty(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)
    resp = client.post(
        "/stock/purchases/receive",
        json={"product_id": product["id"], "qty_base_units": -1, "terminal_id": "T1"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_current_stock_lists_balance_per_product(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product_a = create_product(client, headers, sku="CUR-STK-A")
    product_b = create_product(client, headers, sku="CUR-STK-B")

    client.post(
        "/stock/purchases/receive",
        json={"product_id": product_a["id"], "qty_base_units": 40, "terminal_id": "T1"},
        headers=headers,
    )
    client.post(
        "/stock/adjustments",
        json={"product_id": product_b["id"], "qty_base_units": -3, "terminal_id": "T1"},
        headers=headers,
    )

    resp = client.get("/stock/current", headers=headers)
    assert resp.status_code == 200, resp.text
    rows = {row["product_id"]: row for row in resp.json()}
    assert rows[product_a["id"]]["balance"] == 40
    assert rows[product_b["id"]]["balance"] == -3
    assert rows[product_a["id"]]["sku"] == product_a["sku"]


def test_sales_role_cannot_adjust_stock(client: TestClient, admin_user: User, sales_user: User):
    admin_headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, admin_headers)

    sales_headers = auth_headers(client, "sales1", "salespass")
    resp = client.post(
        "/stock/adjustments",
        json={"product_id": product["id"], "qty_base_units": 10, "terminal_id": "T1"},
        headers=sales_headers,
    )
    assert resp.status_code == 403
