"""Every Platform Admin action, no exceptions — CLAUDE.md's AUDIT
REQUIREMENT. `record()` is the only way a `platform_audit_log` row gets
written; every action endpoint in routers/platform_admin.py calls it in the
same transaction as the change it's recording, so an audit row and its
action either both commit or neither does."""

import uuid

from sqlmodel import Session

from app.models.platform_audit_log import PlatformAuditLog


def record(
    session: Session,
    *,
    platform_admin_id: uuid.UUID,
    action: str,
    tenant_id: uuid.UUID | None,
    old_value: dict | None,
    new_value: dict | None,
    reason: str,
) -> PlatformAuditLog:
    entry = PlatformAuditLog(
        platform_admin_id=platform_admin_id,
        action=action,
        tenant_id=tenant_id,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
    )
    session.add(entry)
    return entry
