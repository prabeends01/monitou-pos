from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(*, subject: str, role: str, tenant_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "role": role, "tenant_id": tenant_id, "aud": "tenant-user", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


PLATFORM_ADMIN_AUDIENCE = "platform-admin"


def create_platform_admin_token(*, subject: str) -> str:
    """A completely separate token space from `create_access_token` — the
    `aud` claim is `platform-admin`, not `tenant-user`, and there is no
    `tenant_id` claim at all (a platform admin isn't scoped to any tenant).
    `get_current_platform_admin` (auth/platform_deps.py) rejects a tenant
    token here and `get_current_user` rejects a platform-admin token there,
    even though both are signed with the same secret — see CLAUDE.md
    Section 11.9.6."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "aud": PLATFORM_ADMIN_AUDIENCE, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decodes without enforcing `aud` here — `verify_aud` is off because
    callers (`get_current_user`, `get_current_platform_admin`) each check
    the claim themselves against the *one* audience value they accept, so
    a tenant-user token is never even superficially valid on a
    platform-admin route or vice versa. jose's built-in audience check
    would otherwise require every caller to pass the expected audience in,
    which is easy to get wrong/omit; an explicit `if payload.get("aud") !=
    ...` in each deps function is harder to silently skip."""
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], options={"verify_aud": False}
        )
    except JWTError as exc:
        raise ValueError("invalid token") from exc
