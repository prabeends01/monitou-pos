import uuid
from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Barcode(SQLModel, table=True):
    __tablename__ = "barcodes"
    __table_args__ = (UniqueConstraint("tenant_id", "barcode_value", name="uq_barcode_tenant_value"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenants.id", index=True)
    product_id: uuid.UUID = Field(foreign_key="products.id", index=True)
    barcode_value: str = Field(index=True)
    pack_qty: int = Field(default=1)
    label: str
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
