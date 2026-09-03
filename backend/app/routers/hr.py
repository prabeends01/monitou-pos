from datetime import date
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.auth.deps import require_role
from app.db import get_session
from app.models.hr import LeaveStatus, TaDaStatus
from app.models.user import User, UserRole
from app.schemas.hr import (
    AttendanceMark,
    AttendanceRead,
    LeaveDecision,
    LeaveRequestCreate,
    LeaveRequestRead,
    TaDaApprove,
    TaDaClaimCreate,
    TaDaClaimRead,
)
from app.services import hr as hr_service
from app.services.entitlements import require_feature
from app.tenancy import get_tenant_owned

router = APIRouter(prefix="/hr", tags=["hr"])


def _require_tenant_user(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    if get_tenant_owned(session, User, user_id, tenant_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="staff member not found")


# --- attendance ---


@router.post("/attendance", response_model=AttendanceRead)
async def mark_attendance(
    payload: AttendanceMark,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("ATTENDANCE_TRACKING")),
) -> AttendanceRead:
    _require_tenant_user(session, admin.tenant_id, payload.user_id)
    record = hr_service.mark_attendance(
        session,
        tenant_id=admin.tenant_id,
        marked_by=admin.id,
        user_id=payload.user_id,
        work_date=payload.work_date,
        status_=payload.status,
        check_in_at=payload.check_in_at,
        check_out_at=payload.check_out_at,
        notes=payload.notes,
    )
    return AttendanceRead.model_validate(record, from_attributes=True)


@router.get("/attendance", response_model=list[AttendanceRead])
async def list_attendance(
    work_date: date | None = Query(default=None),
    user_id: uuid.UUID | None = Query(default=None),
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("ATTENDANCE_TRACKING")),
) -> list[AttendanceRead]:
    records = hr_service.list_attendance(session, admin.tenant_id, work_date=work_date, user_id=user_id)
    return [AttendanceRead.model_validate(r, from_attributes=True) for r in records]


# --- leave ---


@router.post("/leave", response_model=LeaveRequestRead, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    payload: LeaveRequestCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("LEAVE_MANAGEMENT")),
) -> LeaveRequestRead:
    _require_tenant_user(session, admin.tenant_id, payload.user_id)
    request = hr_service.create_leave_request(
        session,
        tenant_id=admin.tenant_id,
        requested_by=admin.id,
        user_id=payload.user_id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
    )
    return LeaveRequestRead.model_validate(request, from_attributes=True)


@router.get("/leave", response_model=list[LeaveRequestRead])
async def list_leave_requests(
    status_filter: LeaveStatus | None = Query(default=None, alias="status"),
    user_id: uuid.UUID | None = Query(default=None),
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("LEAVE_MANAGEMENT")),
) -> list[LeaveRequestRead]:
    requests = hr_service.list_leave_requests(session, admin.tenant_id, status_=status_filter, user_id=user_id)
    return [LeaveRequestRead.model_validate(r, from_attributes=True) for r in requests]


@router.post("/leave/{request_id}/approve", response_model=LeaveRequestRead)
async def approve_leave_request(
    request_id: uuid.UUID,
    _payload: LeaveDecision = LeaveDecision(),
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("LEAVE_MANAGEMENT")),
) -> LeaveRequestRead:
    request = hr_service.decide_leave_request(
        session, tenant_id=admin.tenant_id, request_id=request_id, decided_by=admin.id, new_status=LeaveStatus.approved
    )
    return LeaveRequestRead.model_validate(request, from_attributes=True)


@router.post("/leave/{request_id}/reject", response_model=LeaveRequestRead)
async def reject_leave_request(
    request_id: uuid.UUID,
    _payload: LeaveDecision = LeaveDecision(),
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("LEAVE_MANAGEMENT")),
) -> LeaveRequestRead:
    request = hr_service.decide_leave_request(
        session, tenant_id=admin.tenant_id, request_id=request_id, decided_by=admin.id, new_status=LeaveStatus.rejected
    )
    return LeaveRequestRead.model_validate(request, from_attributes=True)


# --- ta/da ---


@router.post("/ta-da", response_model=TaDaClaimRead, status_code=status.HTTP_201_CREATED)
async def create_ta_da_claim(
    payload: TaDaClaimCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("TA_DA_CLAIMS")),
) -> TaDaClaimRead:
    _require_tenant_user(session, admin.tenant_id, payload.user_id)
    claim = hr_service.create_ta_da_claim(
        session,
        tenant_id=admin.tenant_id,
        requested_by=admin.id,
        user_id=payload.user_id,
        claim_date=payload.claim_date,
        purpose=payload.purpose,
        from_location=payload.from_location,
        to_location=payload.to_location,
        travel_mode=payload.travel_mode,
        amount_claimed=payload.amount_claimed,
    )
    return TaDaClaimRead.model_validate(claim, from_attributes=True)


@router.get("/ta-da", response_model=list[TaDaClaimRead])
async def list_ta_da_claims(
    status_filter: TaDaStatus | None = Query(default=None, alias="status"),
    user_id: uuid.UUID | None = Query(default=None),
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("TA_DA_CLAIMS")),
) -> list[TaDaClaimRead]:
    claims = hr_service.list_ta_da_claims(session, admin.tenant_id, status_=status_filter, user_id=user_id)
    return [TaDaClaimRead.model_validate(c, from_attributes=True) for c in claims]


@router.post("/ta-da/{claim_id}/approve", response_model=TaDaClaimRead)
async def approve_ta_da_claim(
    claim_id: uuid.UUID,
    payload: TaDaApprove = TaDaApprove(),
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("TA_DA_CLAIMS")),
) -> TaDaClaimRead:
    claim = hr_service.decide_ta_da_claim(
        session,
        tenant_id=admin.tenant_id,
        claim_id=claim_id,
        decided_by=admin.id,
        new_status=TaDaStatus.approved,
        amount_approved=payload.amount_approved,
    )
    return TaDaClaimRead.model_validate(claim, from_attributes=True)


@router.post("/ta-da/{claim_id}/reject", response_model=TaDaClaimRead)
async def reject_ta_da_claim(
    claim_id: uuid.UUID,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("TA_DA_CLAIMS")),
) -> TaDaClaimRead:
    claim = hr_service.decide_ta_da_claim(
        session, tenant_id=admin.tenant_id, claim_id=claim_id, decided_by=admin.id, new_status=TaDaStatus.rejected
    )
    return TaDaClaimRead.model_validate(claim, from_attributes=True)


@router.post("/ta-da/{claim_id}/mark-paid", response_model=TaDaClaimRead)
async def mark_ta_da_claim_paid(
    claim_id: uuid.UUID,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("TA_DA_CLAIMS")),
) -> TaDaClaimRead:
    claim = hr_service.decide_ta_da_claim(
        session, tenant_id=admin.tenant_id, claim_id=claim_id, decided_by=admin.id, new_status=TaDaStatus.paid
    )
    return TaDaClaimRead.model_validate(claim, from_attributes=True)
