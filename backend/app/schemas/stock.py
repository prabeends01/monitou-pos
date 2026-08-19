import uuid

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
