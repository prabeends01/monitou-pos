import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    sku: str = Field(unique=True, index=True)
    name: str
    category: str = Field(index=True)
    compatible_models: str | None = None
    base_unit: str = Field(default="piece")
    cost_price: Decimal = Field(max_digits=12, decimal_places=2)
    sale_price: Decimal = Field(max_digits=12, decimal_places=2)
    reorder_threshold: int = Field(default=0)
    is_active: bool = Field(default=True)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
