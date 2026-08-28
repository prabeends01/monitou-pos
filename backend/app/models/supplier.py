import uuid

from sqlmodel import Field, SQLModel


class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenants.id", index=True)
    name: str
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    address: str | None = None
