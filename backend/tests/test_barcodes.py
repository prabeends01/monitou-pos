from fastapi.testclient import TestClient

from app.models.user import User
from tests.test_products import auth_headers, create_product


def create_barcode(client: TestClient, headers: dict, product_id: str, value: str, pack_qty: int, label: str) -> dict:
    resp = client.post(
        "/barcodes",
        json={"product_id": product_id, "barcode_value": value, "pack_qty": pack_qty, "label": label},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_scan_loose_barcode_resolves_single_base_unit(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)
    create_barcode(client, headers, product["id"], "8900000000011", 1, "Single piece")

    resp = client.get("/barcodes/8900000000011", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_units_per_scan"] == 1
    assert body["product_sku"] == product["sku"]


def test_scan_box_barcode_resolves_pack_multiplier(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)
    create_barcode(client, headers, product["id"], "8900000000028", 100, "Box of 100")

    resp = client.get("/barcodes/8900000000028", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_units_per_scan"] == 100
    assert body["barcode"]["label"] == "Box of 100"


def test_duplicate_barcode_value_rejected(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)
    create_barcode(client, headers, product["id"], "8900000000011", 1, "Single piece")
    resp = client.post(
        "/barcodes",
        json={"product_id": product["id"], "barcode_value": "8900000000011", "pack_qty": 1, "label": "dup"},
        headers=headers,
    )
    assert resp.status_code == 409


def test_search_matches_barcode_sku_or_name(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers)  # sku=FST-M10-BOLT, name="M10 Hex Bolt"
    create_barcode(client, headers, product["id"], "8900000000011", 1, "Single piece")

    by_barcode = client.get("/barcodes/search", params={"q": "8900000000011"}, headers=headers)
    assert by_barcode.status_code == 200
    assert len(by_barcode.json()) == 1

    by_sku = client.get("/barcodes/search", params={"q": "M10-BOLT"}, headers=headers)
    assert len(by_sku.json()) == 1
    assert by_sku.json()[0]["product_sku"] == product["sku"]

    by_name = client.get("/barcodes/search", params={"q": "hex"}, headers=headers)
    assert len(by_name.json()) == 1
    assert by_name.json()[0]["product_name"] == product["name"]


def test_search_ranks_exact_match_first(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    exact = create_product(client, headers, sku="BOLT")
    create_barcode(client, headers, exact["id"], "8900000000001", 1, "Single piece")
    other = create_product(client, headers, sku="BOLT-LONG")
    create_barcode(client, headers, other["id"], "8900000000002", 1, "Single piece")

    resp = client.get("/barcodes/search", params={"q": "BOLT"}, headers=headers)
    results = resp.json()
    assert results[0]["product_sku"] == "BOLT"


def test_search_excludes_inactive_products(client: TestClient, admin_user: User):
    headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, headers, sku="OLD-SKU")
    create_barcode(client, headers, product["id"], "8900000099999", 1, "Single piece")
    client.patch(f"/products/{product['id']}", json={"is_active": False}, headers=headers)

    resp = client.get("/barcodes/search", params={"q": "OLD-SKU"}, headers=headers)
    assert resp.json() == []


def test_sales_role_cannot_create_barcode(client: TestClient, admin_user: User, sales_user: User):
    admin_headers = auth_headers(client, "admin1", "adminpass")
    product = create_product(client, admin_headers)

    sales_headers = auth_headers(client, "sales1", "salespass")
    resp = client.post(
        "/barcodes",
        json={"product_id": product["id"], "barcode_value": "1", "pack_qty": 1, "label": "x"},
        headers=sales_headers,
    )
    assert resp.status_code == 403
