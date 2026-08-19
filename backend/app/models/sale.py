import uuid
from datetime import datetime
from decimal import Decimal

from sqlmodel import Field, SQLModel


class Sale(SQLModel, table=True):
    __tablename__ = "sales"

    id: uuid.UUID = Field(primary_key=True)
    invoice_number: str = Field(unique=True, index=True)
    invoice_series: str = Field(index=True)
    customer_id: uuid.UUID | None = Field(default=None, foreign_key="customers.id")
    cashier_id: uuid.UUID = Field(foreign_key="users.id")
    terminal_id: str = Field(index=True)
    total_amount: Decimal = Field(max_digits=12, decimal_places=2)
    gst_amount: Decimal = Field(max_digits=12, decimal_places=2)
    payment_mode: str
    created_at_client: datetime
    synced_at: datetime | None = Field(default=None)


class SaleItem(SQLModel, table=True):
    __tablename__ = "sale_items"

    id: uuid.UUID = Field(primary_key=True)
    sale_id: uuid.UUID = Field(foreign_key="sales.id", index=True)
    product_id: uuid.UUID = Field(foreign_key="products.id", index=True)
    barcode_id: uuid.UUID | None = Field(default=None, foreign_key="barcodes.id")
    qty_base_units: int
    unit_price: Decimal = Field(max_digits=12, decimal_places=2)
