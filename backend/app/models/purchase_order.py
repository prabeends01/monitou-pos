import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlmodel import Field, SQLModel


class PurchaseOrderStatus(str, Enum):
    draft = "draft"
    ordered = "ordered"
    partially_received = "partially_received"
    received = "received"
    cancelled = "cancelled"


class PurchaseOrder(SQLModel, table=True):
    __tablename__ = "purchase_orders"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    supplier_id: uuid.UUID = Field(foreign_key="suppliers.id", index=True)
    status: PurchaseOrderStatus = Field(default=PurchaseOrderStatus.draft)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PurchaseOrderItem(SQLModel, table=True):
    __tablename__ = "purchase_order_items"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    purchase_order_id: uuid.UUID = Field(foreign_key="purchase_orders.id", index=True)
    product_id: uuid.UUID = Field(foreign_key="products.id", index=True)
    qty_base_units: int
    unit_cost: Decimal = Field(max_digits=12, decimal_places=2)
