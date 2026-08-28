from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_role
from app.auth.security import hash_password
from app.db import get_session
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserRead
from app.services.usage_limits import check_limit, increment_usage
from app.tenancy import tenant_scoped

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("", response_model=list[UserRead])
async def list_users(
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
) -> list[User]:
    return list(session.exec(tenant_scoped(User, admin.tenant_id)))


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
) -> User:
    exists = session.exec(
        select(User).where(User.tenant_id == admin.tenant_id, User.username == payload.username)
    ).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already exists")

    check_limit(session, admin.tenant_id, "MAX_USERS")

    user = User(
        tenant_id=admin.tenant_id,
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    increment_usage(session, admin.tenant_id, "MAX_USERS")
    return user
