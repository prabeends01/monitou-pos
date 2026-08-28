"""Create (or confirm) one platform admin account. Idempotent — safe to run
on every deploy. Credentials come from environment variables so a real
deploy never has a hard-coded password in source; falls back to a
clearly-marked dev default only when neither is set (local/dev use).

Run: uv run python -m app.seed_platform_admin
"""

import os

from sqlmodel import Session, select

from app.auth.security import hash_password
from app.db import engine
from app.models.platform_admin import PlatformAdmin

DEFAULT_DEV_USERNAME = "platform-admin"
DEFAULT_DEV_PASSWORD = "change-me-dev-only"  # noqa: S105 — dev fallback only, never used if env vars are set


def seed_platform_admin() -> None:
    username = os.environ.get("PLATFORM_ADMIN_USERNAME", DEFAULT_DEV_USERNAME)
    password = os.environ.get("PLATFORM_ADMIN_PASSWORD")

    with Session(engine) as session:
        existing = session.exec(select(PlatformAdmin).where(PlatformAdmin.username == username)).first()
        if existing is not None:
            print(f"platform admin '{username}' already exists, skipping")
            return

        if password is None:
            password = DEFAULT_DEV_PASSWORD
            print(
                "WARNING: PLATFORM_ADMIN_PASSWORD not set — using an insecure dev-only default. "
                "Set PLATFORM_ADMIN_USERNAME/PLATFORM_ADMIN_PASSWORD before running this against "
                "anything but a local dev database."
            )

        admin = PlatformAdmin(username=username, password_hash=hash_password(password))
        session.add(admin)
        session.commit()
        print(f"created platform admin '{username}'")


if __name__ == "__main__":
    seed_platform_admin()
