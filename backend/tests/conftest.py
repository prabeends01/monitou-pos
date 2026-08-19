import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.auth.security import hash_password
from app.db import get_session
from app.main import app
from app.models.user import User, UserRole


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
def admin_user(session: Session) -> User:
    user = User(username="admin1", password_hash=hash_password("adminpass"), role=UserRole.admin)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def sales_user(session: Session) -> User:
    user = User(username="sales1", password_hash=hash_password("salespass"), role=UserRole.sales)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
