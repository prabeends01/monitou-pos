from fastapi.testclient import TestClient

from app.models.user import User
from tests.conftest import OTHER_TENANT_CODE, TEST_TENANT_CODE


def login(client: TestClient, username: str, password: str, tenant_code: str = TEST_TENANT_CODE) -> str:
    resp = client.post(
        "/auth/login", data={"username": username, "password": password, "client_id": tenant_code}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_login_success(client: TestClient, admin_user: User):
    resp = client.post(
        "/auth/login",
        data={"username": "admin1", "password": "adminpass", "client_id": TEST_TENANT_CODE},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "admin"
    assert body["access_token"]


def test_login_wrong_password(client: TestClient, admin_user: User):
    resp = client.post(
        "/auth/login",
        data={"username": "admin1", "password": "wrong", "client_id": TEST_TENANT_CODE},
    )
    assert resp.status_code == 401


def test_login_wrong_tenant_code(client: TestClient, admin_user: User):
    """Right username/password, wrong tenant_code — must fail exactly like a
    wrong password, not reveal that the username exists elsewhere."""
    resp = client.post(
        "/auth/login",
        data={"username": "admin1", "password": "adminpass", "client_id": "NO-SUCH-TENANT"},
    )
    assert resp.status_code == 401


def test_login_same_username_different_tenants(client: TestClient, admin_user: User, other_tenant_admin_user: User):
    """`admin1` exists in both Tenant A and Tenant B with different
    passwords — usernames are only unique per tenant, not globally."""
    resp = client.post(
        "/auth/login",
        data={"username": "admin1", "password": "otherpass", "client_id": OTHER_TENANT_CODE},
    )
    assert resp.status_code == 200

    resp = client.post(
        "/auth/login",
        data={"username": "admin1", "password": "otherpass", "client_id": TEST_TENANT_CODE},
    )
    assert resp.status_code == 401


def test_me_requires_token(client: TestClient):
    resp = client.get("/users/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client: TestClient, sales_user: User):
    token = login(client, "sales1", "salespass")
    resp = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "sales1"


def test_sales_role_blocked_from_admin_route(client: TestClient, sales_user: User):
    token = login(client, "sales1", "salespass")
    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_role_allowed_on_admin_route(client: TestClient, admin_user: User):
    token = login(client, "admin1", "adminpass")
    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
