from fastapi.testclient import TestClient

from app.models.user import User
from tests.test_auth import login


def auth_headers(client: TestClient, username: str, password: str) -> dict:
    return {"Authorization": f"Bearer {login(client, username, password)}"}


def create_product(client: TestClient, headers: dict, sku: str = "FST-M10-BOLT") -> dict:
    resp = client.post(
        "/products",
        json={
            "sku": sku,
            "name": "M10 Hex Bolt",
            "category": "fasteners",
            "base_unit": "piece",
            "cost_price": "3.50",
            "sale_price": "5.00",
            "reorder_threshold": 200,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_sales_role_cannot_create_product(client: TestClient, sales_user: User):
    headers = auth_headers(client, "sales1", "salespass")
    resp = client.post(
        "/products",
        json={
            "sku": "X",
            "name": "X",
            "category": "x",
            "cost_price": "1",
            "sale_price": "2",
        },
        headers=headers,
    )
    assert resp.status_code == 403


def test_admin_creates_product_and_sees_cost_price(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)
    assert product["cost_price"] == "3.50"

    resp = client.get(f"/products/{product['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["cost_price"] == "3.50"


def test_sales_role_read_hides_cost_price(client: TestClient, admin_user: User, sales_user: User):
    admin_headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, admin_headers)

    sales_headers = auth_headers(client, "sales1", "salespass")
    resp = client.get(f"/products/{product['id']}", headers=sales_headers)
    assert resp.status_code == 200
    assert "cost_price" not in resp.json()
    assert resp.json()["sale_price"] == "5.00"


def test_duplicate_sku_rejected(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    create_product(client, headers)
    resp = client.post(
        "/products",
        json={
            "sku": "FST-M10-BOLT",
            "name": "dup",
            "category": "fasteners",
            "cost_price": "1",
            "sale_price": "2",
        },
        headers=headers,
    )
    assert resp.status_code == 409
