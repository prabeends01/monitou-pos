import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ProductCreate(BaseModel):
    sku: str
    name: str
    category: str
    compatible_models: str | None = None
    base_unit: str = "piece"
    cost_price: Decimal
    sale_price: Decimal
    reorder_threshold: int = 0


class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    compatible_models: str | None = None
    base_unit: str | None = None
    cost_price: Decimal | None = None
    sale_price: Decimal | None = None
    reorder_threshold: int | None = None
    is_active: bool | None = None


class ProductRead(BaseModel):
    """Full view — admin only. Includes cost_price."""

    id: uuid.UUID
    sku: str
    name: str
    category: str
    compatible_models: str | None
    base_unit: str
    cost_price: Decimal
    sale_price: Decimal
    reorder_threshold: int
    is_active: bool
    updated_at: datetime


class ProductReadPublic(BaseModel):
    """Sales-role view — cost_price excluded."""

    id: uuid.UUID
    sku: str
    name: str
    category: str
    compatible_models: str | None
    base_unit: str
    sale_price: Decimal
    reorder_threshold: int
    is_active: bool
    updated_at: datetime
