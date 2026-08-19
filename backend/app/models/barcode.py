import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Barcode(SQLModel, table=True):
    __tablename__ = "barcodes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    product_id: uuid.UUID = Field(foreign_key="products.id", index=True)
    barcode_value: str = Field(unique=True, index=True)
    pack_qty: int = Field(default=1)
    label: str
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
