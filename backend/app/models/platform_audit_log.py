import uuid
from datetime import datetime, timezone

from sqlmodel import JSON, Column, Field, SQLModel


class PlatformAuditLog(SQLModel, table=True):
    """Every Platform Admin action, unconditionally — CLAUDE.md's AUDIT
    REQUIREMENT: plan changes, feature/limit overrides, subscription
    extensions, suspension, reactivation. Records who, when, old value, new
    value, reason. Append-only — routers must never update or delete a row
    here, only insert (same "ledger, not editable rows" principle Section 4
    already applies to `stock_movements`)."""

    __tablename__ = "platform_audit_log"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    platform_admin_id: uuid.UUID = Field(foreign_key="platform_admins.id", index=True)
    action: str = Field(index=True)
    tenant_id: uuid.UUID | None = Field(default=None, foreign_key="tenants.id", index=True)
    old_value: dict | None = Field(default=None, sa_column=Column(JSON))
    new_value: dict | None = Field(default=None, sa_column=Column(JSON))
    reason: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
