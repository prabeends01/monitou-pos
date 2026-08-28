import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.auth.security import decode_access_token
from app.db import get_session
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole
from app.services.subscription_lifecycle import sync_subscription_status
from app.tenancy import set_rls_tenant

SUSPENDED_ERROR = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail={"code": "TENANT_SUSPENDED", "message": "This account has been suspended."},
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise credentials_error from exc

    if payload.get("aud") != "tenant-user":
        raise credentials_error  # e.g. a platform-admin token presented here

    user_id = payload.get("sub")
    token_tenant_id = payload.get("tenant_id")
    if user_id is None or token_tenant_id is None:
        raise credentials_error

    user = session.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise credentials_error

    # the token's tenant_id must still match the user's actual tenant_id —
    # catches a stale token surviving a (hypothetical future) tenant
    # reassignment, and any attempt to present a token for a tenant the
    # user doesn't belong to.
    if str(user.tenant_id) != token_tenant_id:
        raise credentials_error

    # Re-derive the subscription's lifecycle status from today's date on
    # every request (Section 11.8) — cheap (one row lookup, only writes on
    # an actual transition) and means a tenant's final GRACE_PERIOD ->
    # SUSPENDED cutoff takes effect on its very next request, not whenever
    # some batch job next happens to run.
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None:
        raise credentials_error
    sync_subscription_status(session, tenant)
    if tenant.status == TenantStatus.suspended:
        raise SUSPENDED_ERROR

    set_rls_tenant(session, user.tenant_id)
    return user


def get_current_tenant(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Tenant:
    """`get_current_user` above already blocks a suspended tenant before
    this ever runs — this exists for routes that need the `Tenant` row
    itself, not as a second enforcement point."""
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="could not validate credentials")
    return tenant


def require_role(role: UserRole) -> Callable[[User], User]:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="insufficient permissions",
            )
        return user

    return dependency
