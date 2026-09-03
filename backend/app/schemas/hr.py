import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.hr import AttendanceStatus, LeaveStatus, LeaveType, TaDaStatus


class AttendanceMark(BaseModel):
    user_id: uuid.UUID
    work_date: date
    status: AttendanceStatus
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    notes: str | None = None


class AttendanceRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    work_date: date
    status: AttendanceStatus
    check_in_at: datetime | None
    check_out_at: datetime | None
    marked_by: uuid.UUID
    notes: str | None
    updated_at: datetime


class LeaveRequestCreate(BaseModel):
    user_id: uuid.UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str


class LeaveDecision(BaseModel):
    reason: str | None = None


class LeaveRequestRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    days_count: Decimal
    reason: str
    status: LeaveStatus
    requested_by: uuid.UUID
    requested_at: datetime
    decided_by: uuid.UUID | None
    decided_at: datetime | None


class TaDaClaimCreate(BaseModel):
    user_id: uuid.UUID
    claim_date: date
    purpose: str
    from_location: str | None = None
    to_location: str | None = None
    travel_mode: str | None = None
    amount_claimed: Decimal


class TaDaApprove(BaseModel):
    amount_approved: Decimal | None = None


class TaDaClaimRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    claim_date: date
    purpose: str
    from_location: str | None
    to_location: str | None
    travel_mode: str | None
    amount_claimed: Decimal
    amount_approved: Decimal | None
    status: TaDaStatus
    requested_by: uuid.UUID
    requested_at: datetime
    decided_by: uuid.UUID | None
    decided_at: datetime | None
