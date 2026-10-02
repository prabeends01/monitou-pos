import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class StockAdjustmentCreate(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    product_id: uuid.UUID
    qty_base_units: int
    terminal_id: str


class PurchaseReceiveCreate(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    product_id: uuid.UUID
    qty_base_units: int
    terminal_id: str
    reference_id: uuid.UUID | None = None


class StockMovementResult(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    qty_base_units: int
    movement_type: str
    balance_after: int
    went_negative: bool


class StockBalance(BaseModel):
    product_id: uuid.UUID
    balance: int


class CurrentStockRow(BaseModel):
    product_id: uuid.UUID
    sku: str
    name: str
    oem_part_number: str | None = None
    category: str
    subcategory: str | None = None
    brand: str | None = None
    base_unit: str
    warehouse: str | None = None
    rack: str | None = None
    bin_location: str | None = None
    on_hand_qty: int
    reserved_qty: int = 0
    available_qty: int
    on_order_qty: int = 0
    reorder_threshold: int
    safety_stock: int | None = None
    max_stock: int | None = None
    supplier_name: str | None = None
    supplier_code: str | None = None
    lead_time_days: int | None = None
    min_order_qty: int | None = None
    cost_price: Decimal
    sale_price: Decimal
    gst_percent: Decimal
    critical_part: bool
