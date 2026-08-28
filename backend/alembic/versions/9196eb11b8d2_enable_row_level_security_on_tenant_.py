"""enable row level security on tenant-owned tables

Revision ID: 9196eb11b8d2
Revises: 4c4b99b6eb8b
Create Date: 2026-08-28 20:24:40.699769

Defense-in-depth for tenant isolation (CLAUDE.md Section 11.2): even if a
router forgets a `.where(tenant_id == ...)` filter, Postgres itself refuses
to return or accept rows for a different tenant. `FORCE ROW LEVEL SECURITY`
is required because this app currently connects as the table-owning role —
without FORCE, Postgres exempts the owner from its own table's policies.

`app.set_rls_tenant()` (app/tenancy.py) issues `SET LOCAL app.tenant_id`
once per request, right after authentication — see `auth/deps.py::
get_current_user`. `current_setting('app.tenant_id', true)` returns NULL
when unset (e.g. a session that never authenticated), which matches no
rows — fails closed, not open.

Scope: the 10 tables that already exist as tenant-owned business data.
`tenant_feature_overrides` / `tenant_limit_overrides` / `subscriptions` /
`usage_counters` are also tenant-owned but are read/written by Platform
Admin across every tenant at once (Stage 11) — RLS for those needs a
platform-admin bypass role decided at that stage, not before; adding it now
would just get switched off again.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9196eb11b8d2'
down_revision: Union[str, Sequence[str], None] = '4c4b99b6eb8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = [
    "users",
    "products",
    "barcodes",
    "stock_movements",
    "suppliers",
    "customers",
    "purchase_orders",
    "purchase_order_items",
    "sales",
    "sale_items",
]


def upgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
            """
        )


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
