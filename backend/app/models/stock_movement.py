import uuid
from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class MovementType(str, Enum):
    sale = "sale"
    purchase = "purchase"
    adjustment = "adjustment"
    stock_take = "stock_take"
    return_ = "return"
    repack = "repack"


class StockMovement(SQLModel, table=True):
    __tablename__ = "stock_movements"

    id: uuid.UUID = Field(primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenants.id", index=True)
    product_id: uuid.UUID = Field(foreign_key="products.id", index=True)
    qty_base_units: int
    movement_type: MovementType
    reference_id: uuid.UUID | None = Field(default=None, index=True)
    terminal_id: str = Field(index=True)
    created_at_client: datetime
    synced_at: datetime | None = Field(default=None)
