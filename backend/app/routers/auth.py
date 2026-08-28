from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.auth.security import create_access_token, verify_password
from app.db import get_session
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.services.subscription_lifecycle import sync_subscription_status

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Multi-tenant login: `username` is unique per tenant, not globally, so
    the request must also identify the tenant. Carried in the standard
    OAuth2 password-grant form's `client_id` field (sent as the shop/company
    code, e.g. "MONITOU-001") rather than inventing a non-standard field —
    this keeps the request compatible with OAuth2PasswordBearer's tokenUrl
    flow and Swagger's built-in Authorize dialog, which already has a
    client_id input."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="incorrect tenant code, username, or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
    tenant_code = form_data.client_id
    if not tenant_code:
        raise credentials_error

    tenant = session.exec(select(Tenant).where(Tenant.tenant_code == tenant_code)).first()
    if tenant is None:
        raise credentials_error
    sync_subscription_status(session, tenant)  # a login right at the grace-period cutoff must see it too
    if tenant.status == TenantStatus.suspended:
        raise credentials_error

    user = session.exec(
        select(User).where(User.tenant_id == tenant.id, User.username == form_data.username)
    ).first()
    if user is None or not user.is_active or not verify_password(form_data.password, user.password_hash):
        raise credentials_error

    token = create_access_token(subject=str(user.id), role=user.role.value, tenant_id=str(tenant.id))
    return TokenResponse(access_token=token, role=user.role.value)
