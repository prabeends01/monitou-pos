import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class PlatformAdmin(SQLModel, table=True):
    """An internal Monitou platform operator — entirely separate from
    tenant `users` (CLAUDE.md Section 11.13/11.9.6). Never reuse
    `UserRole.admin` for this: a tenant-side privilege-escalation bug must
    not be able to reach platform-admin actions, which is only true if
    these are different tables, different auth, different JWT audience."""

    __tablename__ = "platform_admins"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
