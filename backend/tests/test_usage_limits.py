"""Stage 4 — CLAUDE.md Section 11.4/11.11: usage limit enforcement.
`/users` (MAX_USERS) and `/products` (MAX_SKUS) are the two existing
create-flows wired to `check_limit()`; branches/warehouses have no backing
module yet (Section 11.1) so aren't wired to anything real yet.
"""

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth.security import hash_password
from app.models.entitlement import TenantLimitOverride
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.seed_plans import seed_plans
from app.services.usage_limits import check_limit, get_usage, increment_usage
from tests.test_products import auth_headers


def _tenant_on_plan(session: Session, plan_code: str, tenant_code: str) -> Tenant:
    seed_plans(session)
    plan = session.exec(select(Plan).where(Plan.code == plan_code)).one()
    tenant = Tenant(tenant_code=tenant_code, company_name=tenant_code, active_plan_id=plan.id)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


def _bootstrap_admin(session: Session, tenant: Tenant) -> User:
    """Create the tenant's first user directly (bypassing the API, since we
    need it to exist before we can even log in), and account for it in the
    usage counter — a real `POST /users` call does this atomically, this
    fixture has to do both steps itself."""
    user = User(
        tenant_id=tenant.id, username="admin1", password_hash=hash_password("adminpass"), role=UserRole.admin
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    increment_usage(session, tenant.id, "MAX_USERS")
    return user


def test_basic_tenant_blocks_sixth_active_user(client, session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "LIMIT-BASIC-USERS")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    for i in range(2, 6):  # users 2..5 — brings the tenant to exactly 5, Basic's MAX_USERS
        resp = client.post(
            "/users", json={"username": f"user{i}", "password": "pw12345", "role": "sales"}, headers=headers
        )
        assert resp.status_code == 201, resp.text

    resp = client.post(
        "/users", json={"username": "user6", "password": "pw12345", "role": "sales"}, headers=headers
    )
    assert resp.status_code == 409
    body = resp.json()["detail"]
    assert body == {
        "code": "PLAN_LIMIT_REACHED",
        "limit": "MAX_USERS",
        "limit_value": 5,
        "current_value": 5,
        "message": (
            "Your Basic plan supports up to 5 active users. "
            "Upgrade your plan or purchase additional user capacity."
        ),
    }


def test_essential_tenant_allows_sixth_active_user(client, session: Session):
    """Same shape as the Basic test above, but Essential's MAX_USERS=15
    means the 6th user is nowhere near the limit."""
    tenant = _tenant_on_plan(session, "ESSENTIAL", "LIMIT-ESSENTIAL-USERS")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    for i in range(2, 7):  # users 2..6
        resp = client.post(
            "/users", json={"username": f"user{i}", "password": "pw12345", "role": "sales"}, headers=headers
        )
        assert resp.status_code == 201, resp.text

    assert get_usage(session, tenant.id, "MAX_USERS") == 6


def test_check_limit_raises_at_boundary(session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "LIMIT-BOUNDARY")
    increment_usage(session, tenant.id, "MAX_SKUS", by=5000)  # Basic's exact MAX_SKUS

    with pytest.raises(HTTPException) as exc_info:
        check_limit(session, tenant.id, "MAX_SKUS")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["limit_value"] == 5000
    assert exc_info.value.detail["current_value"] == 5000


def test_check_limit_passes_one_below_boundary(session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "LIMIT-BELOW-BOUNDARY")
    increment_usage(session, tenant.id, "MAX_SKUS", by=4999)
    check_limit(session, tenant.id, "MAX_SKUS")  # does not raise


def test_limit_override_raises_capacity(session: Session):
    """CLAUDE.md's worked example: MAX_USERS override 5 -> 8 for one tenant,
    without changing its plan."""
    tenant = _tenant_on_plan(session, "BASIC", "LIMIT-OVERRIDE")
    increment_usage(session, tenant.id, "MAX_USERS", by=5)

    with pytest.raises(HTTPException):
        check_limit(session, tenant.id, "MAX_USERS")

    session.add(
        TenantLimitOverride(
            tenant_id=tenant.id,
            limit_code="MAX_USERS",
            override_value=8,
            reason="purchased 3 extra user seats",
            approved_by=tenant.id,
        )
    )
    session.commit()

    check_limit(session, tenant.id, "MAX_USERS")  # does not raise — capacity is now 8

    increment_usage(session, tenant.id, "MAX_USERS", by=3)  # now at 8/8
    with pytest.raises(HTTPException):
        check_limit(session, tenant.id, "MAX_USERS")


def test_decrement_usage_frees_capacity(session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "LIMIT-DECREMENT")
    increment_usage(session, tenant.id, "MAX_USERS", by=5)
    with pytest.raises(HTTPException):
        check_limit(session, tenant.id, "MAX_USERS")

    from app.services.usage_limits import decrement_usage

    decrement_usage(session, tenant.id, "MAX_USERS")
    check_limit(session, tenant.id, "MAX_USERS")  # one seat freed, does not raise


def test_creating_sku_over_tenant_specific_override_limit(client, session: Session):
    """End-to-end through the real `/products` endpoint, with a tiny
    override so the test doesn't need to create thousands of rows."""
    tenant = _tenant_on_plan(session, "BASIC", "LIMIT-SKU-OVERRIDE")
    _bootstrap_admin(session, tenant)
    session.add(
        TenantLimitOverride(
            tenant_id=tenant.id, limit_code="MAX_SKUS", override_value=1, reason="test", approved_by=tenant.id
        )
    )
    session.commit()
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    resp = client.post(
        "/products",
        json={"sku": "SKU-1", "name": "x", "category": "x", "cost_price": "1", "sale_price": "2"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    resp = client.post(
        "/products",
        json={"sku": "SKU-2", "name": "y", "category": "y", "cost_price": "1", "sale_price": "2"},
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "PLAN_LIMIT_REACHED"
    assert resp.json()["detail"]["limit"] == "MAX_SKUS"
