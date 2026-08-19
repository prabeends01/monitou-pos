from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_role
from app.db import get_session
from app.models.user import User, UserRole
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("", response_model=list[UserRead])
async def list_users(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role(UserRole.admin)),
) -> list[User]:
    return list(session.exec(select(User)))
