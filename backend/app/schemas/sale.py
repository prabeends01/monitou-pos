import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SaleItemCreate(BaseModel):
    """`qty_base_units` is the final quantity being sold, in base units —
    client-authoritative. Scanning a barcode suggests a default (its
    `pack_qty`, e.g. 100 for a box), but the cashier can edit it down for a
    partial sale from an opened box (e.g. 25 of the 100); the server no
    longer re-derives it from `barcode.pack_qty`."""

    id: uuid.UUID
    product_id: uuid.UUID
    barcode_id: uuid.UUID | None = None
    qty_base_units: int
    unit_price: Decimal


class SaleCreate(BaseModel):
    """`invoice_number` is optional — if omitted, the server assigns the
    next sequential number for `invoice_series` (see services/sales.py).
    Now that the client always talks to the server directly (no offline
    queue), server-side assignment is simpler and avoids any chance of two
    terminals independently picking the same number."""

    id: uuid.UUID
    invoice_number: str | None = None
    invoice_series: str
    terminal_id: str
    customer_id: uuid.UUID | None = None
    payment_mode: str
    gst_amount: Decimal
    created_at_client: datetime
    items: list[SaleItemCreate]


class SaleItemRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    barcode_id: uuid.UUID | None
    qty_base_units: int
    unit_price: Decimal


class SaleRead(BaseModel):
    id: uuid.UUID
    invoice_number: str
    invoice_series: str
    customer_id: uuid.UUID | None
    cashier_id: uuid.UUID
    terminal_id: str
    total_amount: Decimal
    gst_amount: Decimal
    payment_mode: str
    created_at_client: datetime
    synced_at: datetime | None
    items: list[SaleItemRead]
