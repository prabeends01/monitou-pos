import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.auth.security import PLATFORM_ADMIN_AUDIENCE, decode_access_token
from app.db import get_session
from app.models.platform_admin import PlatformAdmin

# a distinct tokenUrl from the tenant-user scheme (auth/deps.py) — separate
# entry in Swagger's Authorize dialog, and a visibly different credential
# space from the tenant login (CLAUDE.md Section 11.13).
platform_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/platform-admin/auth/login")


def get_current_platform_admin(
    token: str = Depends(platform_oauth2_scheme),
    session: Session = Depends(get_session),
) -> PlatformAdmin:
    """Never accepts a tenant-user token, even one for an admin-role user —
    this is a completely separate credential space (Section 11.9.6), not
    an elevated tenant permission."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise credentials_error from exc

    if payload.get("aud") != PLATFORM_ADMIN_AUDIENCE:
        raise credentials_error

    admin_id = payload.get("sub")
    if admin_id is None:
        raise credentials_error

    admin = session.get(PlatformAdmin, uuid.UUID(admin_id))
    if admin is None or not admin.is_active:
        raise credentials_error

    return admin
