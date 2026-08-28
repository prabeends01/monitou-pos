"""add tenant_id to business tables and per-tenant unique constraints

Revision ID: 4c4b99b6eb8b
Revises: 27ff755cb588
Create Date: 2026-08-28 20:23:43.036190

Backfill strategy (CLAUDE.md Section 11.2): every existing row predates
tenancy, so this migration creates one default tenant
("MONITOU-001" / this shop's original single-tenant dataset), assigns every
existing business row to it, and only then makes tenant_id NOT NULL. A fresh
deploy with no existing rows just gets an unused default tenant row it can
ignore or delete once real tenants are provisioned.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '4c4b99b6eb8b'
down_revision: Union[str, Sequence[str], None] = '27ff755cb588'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

# every business table, in an order safe for backfill (no FK ordering
# constraint applies here since we're only filling a new column)
TENANT_TABLES = [
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


def _add_backfilled_tenant_column(table: str) -> None:
    op.add_column(table, sa.Column("tenant_id", sa.Uuid(), nullable=True))
    op.execute(f"UPDATE {table} SET tenant_id = '{DEFAULT_TENANT_ID}'")
    op.alter_column(table, "tenant_id", nullable=False)
    op.create_index(op.f(f"ix_{table}_tenant_id"), table, ["tenant_id"], unique=False)
    op.create_foreign_key(f"fk_{table}_tenant_id_tenants", table, "tenants", ["tenant_id"], ["id"])


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO tenants (id, tenant_code, company_name, active_plan_id, status, created_at, updated_at)
        VALUES ('{DEFAULT_TENANT_ID}', 'MONITOU-001', 'Monitou Spare Parts', NULL, 'active', now(), now())
        ON CONFLICT (tenant_code) DO NOTHING
        """
    )

    for table in TENANT_TABLES:
        _add_backfilled_tenant_column(table)

    # global unique indexes become per-tenant unique constraints
    op.drop_index(op.f('ix_barcodes_barcode_value'), table_name='barcodes')
    op.create_index(op.f('ix_barcodes_barcode_value'), 'barcodes', ['barcode_value'], unique=False)
    op.create_unique_constraint('uq_barcode_tenant_value', 'barcodes', ['tenant_id', 'barcode_value'])

    op.drop_index(op.f('ix_products_sku'), table_name='products')
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=False)
    op.create_unique_constraint('uq_product_tenant_sku', 'products', ['tenant_id', 'sku'])

    op.drop_index(op.f('ix_sales_invoice_number'), table_name='sales')
    op.create_index(op.f('ix_sales_invoice_number'), 'sales', ['invoice_number'], unique=False)
    op.create_unique_constraint('uq_sale_tenant_invoice_number', 'sales', ['tenant_id', 'invoice_number'])

    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=False)
    op.create_unique_constraint('uq_user_tenant_username', 'users', ['tenant_id', 'username'])


def downgrade() -> None:
    op.drop_constraint('uq_user_tenant_username', 'users', type_='unique')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    op.drop_constraint('uq_sale_tenant_invoice_number', 'sales', type_='unique')
    op.drop_index(op.f('ix_sales_invoice_number'), table_name='sales')
    op.create_index(op.f('ix_sales_invoice_number'), 'sales', ['invoice_number'], unique=True)

    op.drop_constraint('uq_product_tenant_sku', 'products', type_='unique')
    op.drop_index(op.f('ix_products_sku'), table_name='products')
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=True)

    op.drop_constraint('uq_barcode_tenant_value', 'barcodes', type_='unique')
    op.drop_index(op.f('ix_barcodes_barcode_value'), table_name='barcodes')
    op.create_index(op.f('ix_barcodes_barcode_value'), 'barcodes', ['barcode_value'], unique=True)

    for table in reversed(TENANT_TABLES):
        op.drop_constraint(f"fk_{table}_tenant_id_tenants", table, type_='foreignkey')
        op.drop_index(op.f(f"ix_{table}_tenant_id"), table_name=table)
        op.drop_column(table, 'tenant_id')

    op.execute(f"DELETE FROM tenants WHERE id = '{DEFAULT_TENANT_ID}'")
