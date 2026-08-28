import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from sqlmodel import select

from app.auth.security import hash_password
from app.db import get_session
from app.main import app
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.seed_plans import seed_plans

TEST_TENANT_CODE = "TEST-TENANT-A"
OTHER_TENANT_CODE = "TEST-TENANT-B"

# Existing tests predate the plan/entitlement system and don't exercise
# plan-specific feature/limit behavior — they just need a plan with enough
# headroom (Enterprise: 30 users, 50000 SKUs) that check_limit() never
# trips on the handful of rows a test creates. Tests that specifically
# exercise plan differences (test_entitlements.py, future limit tests) seed
# their own tenants with a specific plan instead of using this fixture.
DEFAULT_TEST_PLAN_CODE = "ENTERPRISE"


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def _default_plan(session: Session) -> Plan:
    seed_plans(session)
    return session.exec(select(Plan).where(Plan.code == DEFAULT_TEST_PLAN_CODE)).one()


@pytest.fixture
def tenant(session: Session, _default_plan: Plan) -> Tenant:
    tenant = Tenant(tenant_code=TEST_TENANT_CODE, company_name="Test Tenant A", active_plan_id=_default_plan.id)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


@pytest.fixture
def other_tenant(session: Session, _default_plan: Plan) -> Tenant:
    tenant = Tenant(tenant_code=OTHER_TENANT_CODE, company_name="Test Tenant B", active_plan_id=_default_plan.id)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


@pytest.fixture
def admin_user(session: Session, tenant: Tenant) -> User:
    user = User(
        tenant_id=tenant.id, username="admin1", password_hash=hash_password("adminpass"), role=UserRole.admin
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def sales_user(session: Session, tenant: Tenant) -> User:
    user = User(
        tenant_id=tenant.id, username="sales1", password_hash=hash_password("salespass"), role=UserRole.sales
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def other_tenant_admin_user(session: Session, other_tenant: Tenant) -> User:
    user = User(
        tenant_id=other_tenant.id,
        username="admin1",  # deliberately same username as `admin_user` — different tenant, must not collide
        password_hash=hash_password("otherpass"),
        role=UserRole.admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
