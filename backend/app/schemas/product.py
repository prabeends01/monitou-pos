import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ProductCreate(BaseModel):
    sku: str
    name: str
    oem_part_number: str | None = None
    category: str
    subcategory: str | None = None
    brand: str | None = None
    compatible_models: str | None = None
    base_unit: str = "piece"
    warehouse: str | None = None
    rack: str | None = None
    bin_location: str | None = None
    supplier_name: str | None = None
    supplier_code: str | None = None
    lead_time_days: int | None = None
    min_order_qty: int | None = None
    cost_price: Decimal
    sale_price: Decimal
    gst_percent: Decimal = Decimal(18)
    reorder_threshold: int = 0
    safety_stock: int | None = None
    max_stock: int | None = None
    critical_part: bool = False


class ProductUpdate(BaseModel):
    name: str | None = None
    oem_part_number: str | None = None
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    compatible_models: str | None = None
    base_unit: str | None = None
    warehouse: str | None = None
    rack: str | None = None
    bin_location: str | None = None
    supplier_name: str | None = None
    supplier_code: str | None = None
    lead_time_days: int | None = None
    min_order_qty: int | None = None
    cost_price: Decimal | None = None
    sale_price: Decimal | None = None
    gst_percent: Decimal | None = None
    reorder_threshold: int | None = None
    safety_stock: int | None = None
    max_stock: int | None = None
    critical_part: bool | None = None
    is_active: bool | None = None


class ProductRead(BaseModel):
    """Full view — admin only. Includes cost_price."""

    id: uuid.UUID
    sku: str
    name: str
    oem_part_number: str | None
    category: str
    subcategory: str | None
    brand: str | None
    compatible_models: str | None
    base_unit: str
    warehouse: str | None
    rack: str | None
    bin_location: str | None
    supplier_name: str | None
    supplier_code: str | None
    lead_time_days: int | None
    min_order_qty: int | None
    cost_price: Decimal
    sale_price: Decimal
    gst_percent: Decimal
    reorder_threshold: int
    safety_stock: int | None
    max_stock: int | None
    critical_part: bool
    is_active: bool
    updated_at: datetime


class ProductReadPublic(BaseModel):
    """Sales-role view — cost_price excluded."""

    id: uuid.UUID
    sku: str
    name: str
    oem_part_number: str | None
    category: str
    subcategory: str | None
    brand: str | None
    compatible_models: str | None
    base_unit: str
    warehouse: str | None
    rack: str | None
    bin_location: str | None
    supplier_name: str | None
    supplier_code: str | None
    lead_time_days: int | None
    min_order_qty: int | None
    sale_price: Decimal
    gst_percent: Decimal
    reorder_threshold: int
    safety_stock: int | None
    max_stock: int | None
    critical_part: bool
    is_active: bool
    updated_at: datetime
