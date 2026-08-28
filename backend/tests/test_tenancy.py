"""Cross-tenant isolation — CLAUDE.md Section 11.11's core security proof.
A user from one tenant must never reach another tenant's rows, even by
guessing/crafting an ID in the request. `tenant_scoped()`/`get_tenant_owned()`
(app/tenancy.py) are what's under test here, indirectly, through the API."""

from fastapi.testclient import TestClient

from app.models.tenant import Tenant
from app.models.user import User
from tests.conftest import OTHER_TENANT_CODE
from tests.test_products import auth_headers, create_product


def test_same_sku_allowed_across_different_tenants(
    client: TestClient, admin_user: User, other_tenant_admin_user: User
):
    """SKU uniqueness is per-tenant (Section 11.9.4) — two unrelated
    customers picking the same SKU must not collide."""
    a_headers = auth_headers(client, "admin1", "adminpass")
    create_product(client, a_headers, sku="SAME-SKU")

    b_headers = auth_headers(client, "admin1", "otherpass", OTHER_TENANT_CODE)
    resp = client.post(
        "/products",
        json={
            "sku": "SAME-SKU",
            "name": "Same SKU, different company",
            "category": "fasteners",
            "cost_price": "1",
            "sale_price": "2",
        },
        headers=b_headers,
    )
    assert resp.status_code == 201, resp.text


def test_tenant_a_cannot_read_tenant_b_product_by_id(
    client: TestClient, admin_user: User, other_tenant_admin_user: User
):
    b_headers = auth_headers(client, "admin1", "otherpass", OTHER_TENANT_CODE)
    b_product = create_product(client, b_headers, sku="TENANT-B-ONLY")

    a_headers = auth_headers(client, "admin1", "adminpass")
    resp = client.get(f"/products/{b_product['id']}", headers=a_headers)
    assert resp.status_code == 404


def test_tenant_a_product_list_excludes_tenant_b(
    client: TestClient, admin_user: User, other_tenant_admin_user: User
):
    a_headers = auth_headers(client, "admin1", "adminpass")
    create_product(client, a_headers, sku="TENANT-A-PRODUCT")

    b_headers = auth_headers(client, "admin1", "otherpass", OTHER_TENANT_CODE)
    create_product(client, b_headers, sku="TENANT-B-PRODUCT")

    resp = client.get("/products", headers=a_headers)
    assert resp.status_code == 200
    skus = {p["sku"] for p in resp.json()}
    assert skus == {"TENANT-A-PRODUCT"}


def test_tenant_a_cannot_deactivate_tenant_b_product(
    client: TestClient, admin_user: User, other_tenant_admin_user: User
):
    b_headers = auth_headers(client, "admin1", "otherpass", OTHER_TENANT_CODE)
    b_product = create_product(client, b_headers, sku="TENANT-B-PROTECTED")

    a_headers = auth_headers(client, "admin1", "adminpass")
    resp = client.delete(f"/products/{b_product['id']}", headers=a_headers)
    assert resp.status_code == 404

    # confirm it's untouched from Tenant B's own view
    resp = client.get(f"/products/{b_product['id']}", headers=b_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


def test_user_list_scoped_to_own_tenant(
    client: TestClient, admin_user: User, other_tenant_admin_user: User, tenant: Tenant
):
    a_headers = auth_headers(client, "admin1", "adminpass")
    resp = client.get("/users", headers=a_headers)
    assert resp.status_code == 200
    assert {u["username"] for u in resp.json()} == {"admin1"}
    assert len(resp.json()) == 1  # not 2, even though "admin1" also exists in the other tenant
