"""Central tenant-scoping helpers. Every query against a tenant-owned table
must go through one of these — never a bare `select(Model)` or
`session.get(Model, id)` on a tenant-owned model. See CLAUDE.md Section 11.2.

This is the application-level enforcement layer. Postgres Row-Level Security
(migration `<rls migration>`) is the defense-in-depth layer underneath it —
this module must not be treated as sufficient on its own reasoning ("we
already filter in Python") to skip enabling RLS on a new tenant-owned table.
"""

import uuid
from typing import TypeVar

from sqlalchemy import text
from sqlmodel import Session, SQLModel, select
from sqlmodel.sql.expression import SelectOfScalar

ModelT = TypeVar("ModelT", bound=SQLModel)


def tenant_scoped(model: type[ModelT], tenant_id: uuid.UUID) -> SelectOfScalar[ModelT]:
    """`select(model)` pre-filtered to one tenant. `model` must declare a
    `tenant_id` column."""
    return select(model).where(model.tenant_id == tenant_id)  # type: ignore[attr-defined]


def get_tenant_owned(session: Session, model: type[ModelT], id_: uuid.UUID, tenant_id: uuid.UUID) -> ModelT | None:
    """`session.get()` that also enforces tenant ownership. Returns None both
    when the row doesn't exist and when it belongs to another tenant — the
    caller should raise the same 404 either way, never revealing that a
    cross-tenant row exists."""
    obj = session.get(model, id_)
    if obj is None or getattr(obj, "tenant_id", None) != tenant_id:
        return None
    return obj


def set_rls_tenant(session: Session, tenant_id: uuid.UUID) -> None:
    """Set the Postgres session variable the RLS policies (migration
    `9196eb11b8d2`) key on, for the lifetime of this request's transaction.
    Called once, from `auth/deps.py::get_current_user`, right after the
    tenant is known. No-op on non-Postgres backends (the pytest fixtures use
    an in-memory SQLite session, which has no RLS and no `SET LOCAL`
    support — those tests rely on `tenant_scoped()`/`get_tenant_owned()`
    application-level filtering alone).

    `tenant_id` is a `uuid.UUID`, so `str()` always yields a well-formed
    UUID literal — this is not string-built from unvalidated input, so
    inlining it into the SQL text is safe despite not using a bind
    parameter (`SET LOCAL` does not accept query bind parameters).
    """
    if session.get_bind().dialect.name != "postgresql":
        return
    session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
