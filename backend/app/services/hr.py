import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.hr import AttendanceRecord, LeaveRequest, LeaveStatus, TaDaClaim, TaDaStatus
from app.tenancy import tenant_scoped


def mark_attendance(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    marked_by: uuid.UUID,
    user_id: uuid.UUID,
    work_date: date,
    status_: str,
    check_in_at: datetime | None,
    check_out_at: datetime | None,
    notes: str | None,
) -> AttendanceRecord:
    """Upsert — one row per (tenant, user, day). Re-marking the same day
    edits the existing row instead of erroring, since admin correcting an
    earlier mistake is the normal case, not an exception."""
    existing = session.exec(
        select(AttendanceRecord).where(
            AttendanceRecord.tenant_id == tenant_id,
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.work_date == work_date,
        )
    ).first()

    if existing is not None:
        existing.status = status_
        existing.check_in_at = check_in_at
        existing.check_out_at = check_out_at
        existing.notes = notes
        existing.marked_by = marked_by
        existing.updated_at = datetime.now(timezone.utc)
        record = existing
    else:
        record = AttendanceRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            work_date=work_date,
            status=status_,
            check_in_at=check_in_at,
            check_out_at=check_out_at,
            notes=notes,
            marked_by=marked_by,
        )

    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_leave_request(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    requested_by: uuid.UUID,
    user_id: uuid.UUID,
    leave_type: str,
    start_date: date,
    end_date: date,
    reason: str,
) -> LeaveRequest:
    if end_date < start_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="end_date before start_date")

    days_count = Decimal((end_date - start_date).days + 1)
    request = LeaveRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        days_count=days_count,
        reason=reason,
        requested_by=requested_by,
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def decide_leave_request(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    request_id: uuid.UUID,
    decided_by: uuid.UUID,
    new_status: LeaveStatus,
) -> LeaveRequest:
    request = session.get(LeaveRequest, request_id)
    if request is None or request.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="leave request not found")
    if request.status != LeaveStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"leave request already {request.status.value}",
        )

    request.status = new_status
    request.decided_by = decided_by
    request.decided_at = datetime.now(timezone.utc)
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def create_ta_da_claim(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    requested_by: uuid.UUID,
    user_id: uuid.UUID,
    claim_date: date,
    purpose: str,
    from_location: str | None,
    to_location: str | None,
    travel_mode: str | None,
    amount_claimed: Decimal,
) -> TaDaClaim:
    if amount_claimed <= 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="amount_claimed must be positive")

    claim = TaDaClaim(
        tenant_id=tenant_id,
        user_id=user_id,
        claim_date=claim_date,
        purpose=purpose,
        from_location=from_location,
        to_location=to_location,
        travel_mode=travel_mode,
        amount_claimed=amount_claimed,
        requested_by=requested_by,
    )
    session.add(claim)
    session.commit()
    session.refresh(claim)
    return claim


def decide_ta_da_claim(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    decided_by: uuid.UUID,
    new_status: TaDaStatus,
    amount_approved: Decimal | None = None,
) -> TaDaClaim:
    claim = session.get(TaDaClaim, claim_id)
    if claim is None or claim.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TA/DA claim not found")

    if new_status == TaDaStatus.paid:
        if claim.status != TaDaStatus.approved:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="only an approved claim can be marked paid")
        claim.status = TaDaStatus.paid
        session.add(claim)
        session.commit()
        session.refresh(claim)
        return claim

    if claim.status != TaDaStatus.pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"claim already {claim.status.value}")

    claim.status = new_status
    claim.decided_by = decided_by
    claim.decided_at = datetime.now(timezone.utc)
    if new_status == TaDaStatus.approved:
        claim.amount_approved = amount_approved if amount_approved is not None else claim.amount_claimed
    session.add(claim)
    session.commit()
    session.refresh(claim)
    return claim


def list_attendance(
    session: Session, tenant_id: uuid.UUID, *, work_date: date | None, user_id: uuid.UUID | None
) -> list[AttendanceRecord]:
    query = tenant_scoped(AttendanceRecord, tenant_id)
    if work_date is not None:
        query = query.where(AttendanceRecord.work_date == work_date)
    if user_id is not None:
        query = query.where(AttendanceRecord.user_id == user_id)
    return list(session.exec(query.order_by(AttendanceRecord.work_date.desc())).all())


def list_leave_requests(
    session: Session, tenant_id: uuid.UUID, *, status_: LeaveStatus | None, user_id: uuid.UUID | None
) -> list[LeaveRequest]:
    query = tenant_scoped(LeaveRequest, tenant_id)
    if status_ is not None:
        query = query.where(LeaveRequest.status == status_)
    if user_id is not None:
        query = query.where(LeaveRequest.user_id == user_id)
    return list(session.exec(query.order_by(LeaveRequest.requested_at.desc())).all())


def list_ta_da_claims(
    session: Session, tenant_id: uuid.UUID, *, status_: TaDaStatus | None, user_id: uuid.UUID | None
) -> list[TaDaClaim]:
    query = tenant_scoped(TaDaClaim, tenant_id)
    if status_ is not None:
        query = query.where(TaDaClaim.status == status_)
    if user_id is not None:
        query = query.where(TaDaClaim.user_id == user_id)
    return list(session.exec(query.order_by(TaDaClaim.requested_at.desc())).all())
