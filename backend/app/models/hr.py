import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class AttendanceStatus(str, Enum):
    present = "present"
    absent = "absent"
    half_day = "half_day"
    on_leave = "on_leave"


class LeaveType(str, Enum):
    casual = "casual"
    sick = "sick"
    earned = "earned"
    unpaid = "unpaid"


class LeaveStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class TaDaStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    paid = "paid"


class AttendanceRecord(SQLModel, table=True):
    """One row per staff member per calendar day — admin-entered, no
    self-check-in in v1 (CLAUDE.md Section 12.1)."""

    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "work_date", name="uq_attendance_tenant_user_date"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenants.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    work_date: date = Field(index=True)
    status: AttendanceStatus
    check_in_at: datetime | None = Field(default=None)
    check_out_at: datetime | None = Field(default=None)
    marked_by: uuid.UUID = Field(foreign_key="users.id")
    notes: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LeaveRequest(SQLModel, table=True):
    """Admin logs and decides leave on behalf of staff — no self-service in
    v1 (CLAUDE.md Section 12.6)."""

    __tablename__ = "leave_requests"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenants.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    leave_type: LeaveType
    start_date: date
    end_date: date
    days_count: Decimal = Field(max_digits=5, decimal_places=1)
    reason: str
    status: LeaveStatus = Field(default=LeaveStatus.pending, index=True)
    requested_by: uuid.UUID = Field(foreign_key="users.id")
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    decided_at: datetime | None = Field(default=None)


class TaDaClaim(SQLModel, table=True):
    """Travel Allowance / Dearness Allowance reimbursement claim, logged and
    decided by admin on behalf of staff — no self-service in v1."""

    __tablename__ = "ta_da_claims"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: uuid.UUID = Field(foreign_key="tenants.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    claim_date: date
    purpose: str
    from_location: str | None = Field(default=None)
    to_location: str | None = Field(default=None)
    travel_mode: str | None = Field(default=None)
    amount_claimed: Decimal = Field(max_digits=12, decimal_places=2)
    amount_approved: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    status: TaDaStatus = Field(default=TaDaStatus.pending, index=True)
    requested_by: uuid.UUID = Field(foreign_key="users.id")
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_by: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    decided_at: datetime | None = Field(default=None)
