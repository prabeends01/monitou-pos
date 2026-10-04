import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_sku"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenants.id", index=True)
    sku: str = Field(index=True)
    name: str
    oem_part_number: str | None = Field(default=None)
    category: str = Field(index=True)
    subcategory: str | None = Field(default=None)
    brand: str | None = Field(default=None)
    compatible_models: str | None = None
    base_unit: str = Field(default="piece")
    warehouse: str | None = Field(default=None)
    rack: str | None = Field(default=None)
    bin_location: str | None = Field(default=None)
    supplier_name: str | None = Field(default=None)
    supplier_code: str | None = Field(default=None)
    lead_time_days: int | None = Field(default=None)
    min_order_qty: int | None = Field(default=None)
    cost_price: Decimal = Field(max_digits=12, decimal_places=2)
    sale_price: Decimal = Field(max_digits=12, decimal_places=2)
    gst_percent: Decimal = Field(default=Decimal(18), max_digits=5, decimal_places=2)
    reorder_threshold: int = Field(default=0)
    safety_stock: int | None = Field(default=None)
    max_stock: int | None = Field(default=None)
    critical_part: bool = Field(default=False)
    is_active: bool = Field(default=True)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), index=True
    )
