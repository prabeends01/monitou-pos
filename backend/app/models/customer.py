import uuid
from decimal import Decimal

from sqlmodel import Field, SQLModel


class Customer(SQLModel, table=True):
    __tablename__ = "customers"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    address: str | None = None
    credit_enabled: bool = Field(default=False)
    outstanding_balance: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=2)
