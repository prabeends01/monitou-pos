"""HR module (CLAUDE.md Section 12) — attendance, leave, TA/DA. Admin-only,
Enterprise-only in the proposed catalog placement (12.3); a sales-role user
never needs to be tested against these routes since `require_role(admin)`
is identical to every other admin-only router already covered elsewhere."""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from tests.test_products import auth_headers
from tests.test_usage_limits import _bootstrap_admin, _tenant_on_plan


def _staff(client: TestClient, headers: dict, username: str = "user2") -> str:
    resp = client.post("/users", json={"username": username, "password": "pw12345", "role": "sales"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_basic_tenant_cannot_reach_attendance(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "BASIC", "HR-BASIC-BLOCKED")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    resp = client.get("/hr/attendance", headers=headers)
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["code"] == "FEATURE_NOT_AVAILABLE"
    assert detail["feature"] == "ATTENDANCE_TRACKING"
    assert detail["required_plan"] == "ENTERPRISE"


def test_mark_attendance_is_idempotent_upsert(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "ENTERPRISE", "HR-ATTENDANCE")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    staff_id = _staff(client, headers)
    today = date.today().isoformat()

    resp = client.post(
        "/hr/attendance", json={"user_id": staff_id, "work_date": today, "status": "present"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    record_id = resp.json()["id"]

    resp = client.post(
        "/hr/attendance", json={"user_id": staff_id, "work_date": today, "status": "half_day"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == record_id, "re-marking the same day edits the row, not a duplicate"
    assert resp.json()["status"] == "half_day"

    resp = client.get(f"/hr/attendance?work_date={today}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_attendance_rejects_staff_from_another_tenant(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "ENTERPRISE", "HR-ATT-TENANT-A")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)

    other_tenant = _tenant_on_plan(session, "ENTERPRISE", "HR-ATT-TENANT-B")
    other_admin = _bootstrap_admin(session, other_tenant)

    resp = client.post(
        "/hr/attendance",
        json={"user_id": str(other_admin.id), "work_date": date.today().isoformat(), "status": "present"},
        headers=headers,
    )
    assert resp.status_code == 404


def test_leave_request_lifecycle(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "ENTERPRISE", "HR-LEAVE")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    staff_id = _staff(client, headers)

    start = date.today()
    end = start + timedelta(days=2)
    resp = client.post(
        "/hr/leave",
        json={
            "user_id": staff_id,
            "leave_type": "casual",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "reason": "personal",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["days_count"] == "3.0"
    request_id = body["id"]

    resp = client.post(f"/hr/leave/{request_id}/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    resp = client.post(f"/hr/leave/{request_id}/reject", headers=headers)
    assert resp.status_code == 409, "an already-decided request cannot be decided again"


def test_leave_rejects_end_before_start(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "ENTERPRISE", "HR-LEAVE-BADRANGE")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    staff_id = _staff(client, headers)

    resp = client.post(
        "/hr/leave",
        json={
            "user_id": staff_id,
            "leave_type": "sick",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() - timedelta(days=1)).isoformat(),
            "reason": "x",
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_ta_da_claim_lifecycle_with_partial_approval(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "ENTERPRISE", "HR-TADA")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    staff_id = _staff(client, headers)

    resp = client.post(
        "/hr/ta-da",
        json={
            "user_id": staff_id,
            "claim_date": date.today().isoformat(),
            "purpose": "site visit",
            "from_location": "Bhubaneswar",
            "to_location": "Cuttack",
            "travel_mode": "bus",
            "amount_claimed": "500.00",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    claim_id = resp.json()["id"]
    assert resp.json()["status"] == "pending"

    resp = client.post(f"/hr/ta-da/{claim_id}/approve", json={"amount_approved": "400.00"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["amount_approved"] == "400.00"

    resp = client.post(f"/hr/ta-da/{claim_id}/mark-paid", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "paid"


def test_ta_da_approve_defaults_amount_approved_to_claimed(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "ENTERPRISE", "HR-TADA-DEFAULT")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    staff_id = _staff(client, headers)

    resp = client.post(
        "/hr/ta-da",
        json={"user_id": staff_id, "claim_date": date.today().isoformat(), "purpose": "x", "amount_claimed": "120.00"},
        headers=headers,
    )
    claim_id = resp.json()["id"]

    resp = client.post(f"/hr/ta-da/{claim_id}/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["amount_approved"] == "120.00"


def test_ta_da_cannot_mark_paid_before_approval(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "ENTERPRISE", "HR-TADA-UNAPPROVED")
    _bootstrap_admin(session, tenant)
    headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    staff_id = _staff(client, headers)

    resp = client.post(
        "/hr/ta-da",
        json={"user_id": staff_id, "claim_date": date.today().isoformat(), "purpose": "x", "amount_claimed": "50.00"},
        headers=headers,
    )
    claim_id = resp.json()["id"]

    resp = client.post(f"/hr/ta-da/{claim_id}/mark-paid", headers=headers)
    assert resp.status_code == 409


def test_sales_role_cannot_mark_attendance(client: TestClient, session: Session):
    tenant = _tenant_on_plan(session, "ENTERPRISE", "HR-RBAC")
    _bootstrap_admin(session, tenant)
    admin_headers = auth_headers(client, "admin1", "adminpass", tenant.tenant_code)
    _staff(client, admin_headers)
    sales_headers = auth_headers(client, "user2", "pw12345", tenant.tenant_code)

    resp = client.get("/hr/attendance", headers=sales_headers)
    assert resp.status_code == 403
