import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BarcodeCreate(BaseModel):
    product_id: uuid.UUID
    barcode_value: str
    pack_qty: int = 1
    label: str


class BarcodeRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    barcode_value: str
    pack_qty: int
    label: str
    updated_at: datetime


class BarcodeScanResult(BaseModel):
    """What POS scanning/search resolves to: which product, how many base
    units this scan represents, and its current sale price — everything
    the POS billing cart needs without a separate product fetch."""

    barcode: BarcodeRead
    product_id: uuid.UUID
    product_sku: str
    product_name: str
    base_units_per_scan: int
    sale_price: Decimal
