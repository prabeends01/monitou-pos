"""Platform Super Admin — CLAUDE.md Section 11.13/Stage 11. Entirely
separate credential space from tenant users (auth/platform_deps.py) and
entirely separate from the tenant-facing routers above. Every mutating
endpoint here writes a `platform_audit_log` row in the same transaction as
its change (services/platform_audit.py) — CLAUDE.md's AUDIT REQUIREMENT.

RLS note: `get_current_platform_admin` does NOT call `tenancy.set_rls_tenant`
(a platform admin isn't scoped to one tenant), so any query here against an
RLS-protected table (Section 11.2 — currently just `users`, `products`,
`barcodes`, `stock_movements`, `suppliers`, `customers`, `purchase_orders`,
`purchase_order_items`, `sales`, `sale_items`) would come back empty under a
real (non-superuser) production DB role, even though the application-level
`WHERE tenant_id = ...` filter is correct — RLS ANDs its own predicate on
top, and that predicate is never true with `app.tenant_id` unset. The one
place this stage touches such a table (`get_tenant_detail`'s user list)
works around it by calling `set_rls_tenant` for that one tenant right
before the query — see the comment there. A durable fix (a `BYPASSRLS`
platform-admin DB role) is an infra decision, not code, and is noted as
still open in CLAUDE.md.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, func, select

from app.auth.platform_deps import get_current_platform_admin
from app.auth.security import create_platform_admin_token, verify_password
from app.db import get_session
from app.models.entitlement import TenantFeatureOverride, TenantLimitOverride
from app.models.plan import Feature, Plan
from app.models.platform_admin import PlatformAdmin
from app.models.platform_audit_log import PlatformAuditLog
from app.models.tenant import Subscription, SubscriptionStatus, Tenant, TenantStatus
from app.models.upgrade_request import UpgradeRequest, UpgradeRequestStatus
from app.models.user import User
from app.plan_catalog import PLAN_LIMITS
from app.schemas.platform_admin import (
    ApproveUpgradeRequestRequest,
    AuditLogEntry,
    ChangePlanRequest,
    DashboardStats,
    ExtendSubscriptionRequest,
    FeatureOverrideRequest,
    LimitOverrideRequest,
    PlanChangeImpact,
    PlatformAdminTokenResponse,
    ReactivateRequest,
    RejectUpgradeRequestRequest,
    RevokePlanRequest,
    SuspendRequest,
    TenantDetail,
    TenantListRow,
    TenantUserRow,
    UpgradeRequestAdminRow,
)
from app.services.entitlements import can_use_feature
from app.services.plan_change import assess_plan_change_impact
from app.services.platform_audit import record as record_audit
from app.services.subscriptions import get_current_subscription
from app.services.usage_limits import get_limit, get_usage
from app.tenancy import set_rls_tenant

router = APIRouter(prefix="/platform-admin", tags=["platform-admin"])

UPCOMING_RENEWAL_WINDOW_DAYS = 30


def _get_tenant_or_404(session: Session, tenant_id: uuid.UUID) -> Tenant:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant not found")
    return tenant


@router.post("/auth/login", response_model=PlatformAdminTokenResponse)
async def platform_admin_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> PlatformAdminTokenResponse:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
    admin = session.exec(select(PlatformAdmin).where(PlatformAdmin.username == form_data.username)).first()
    if admin is None or not admin.is_active or not verify_password(form_data.password, admin.password_hash):
        raise credentials_error
    return PlatformAdminTokenResponse(access_token=create_platform_admin_token(subject=str(admin.id)))


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard(
    session: Session = Depends(get_session),
    _admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> DashboardStats:
    tenants = session.exec(select(Tenant)).all()
    plans_by_id = {p.id: p for p in session.exec(select(Plan)).all()}

    today = date.today()
    horizon = today + timedelta(days=UPCOMING_RENEWAL_WINDOW_DAYS)
    amc_due = 0
    upcoming_renewals = 0
    plan_code_counts: dict[str, int] = {"BASIC": 0, "ESSENTIAL": 0, "ENTERPRISE": 0}

    for tenant in tenants:
        if tenant.active_plan_id and tenant.active_plan_id in plans_by_id:
            code = plans_by_id[tenant.active_plan_id].code
            if code in plan_code_counts:
                plan_code_counts[code] += 1
        subscription = get_current_subscription(session, tenant.id)
        if subscription and subscription.renewal_date:
            if subscription.renewal_date < today:
                amc_due += 1
            elif subscription.renewal_date <= horizon:
                upcoming_renewals += 1

    pending_upgrade_requests = session.exec(
        select(func.count()).select_from(UpgradeRequest).where(UpgradeRequest.status == UpgradeRequestStatus.pending)
    ).one()

    return DashboardStats(
        total_tenants=len(tenants),
        active_tenants=sum(1 for t in tenants if t.status == TenantStatus.active),
        suspended_accounts=sum(1 for t in tenants if t.status == TenantStatus.suspended),
        basic_customers=plan_code_counts["BASIC"],
        essential_customers=plan_code_counts["ESSENTIAL"],
        enterprise_customers=plan_code_counts["ENTERPRISE"],
        amc_due=amc_due,
        upcoming_renewals=upcoming_renewals,
        pending_upgrade_requests=pending_upgrade_requests,
    )


@router.get("/tenants", response_model=list[TenantListRow])
async def list_tenants(
    session: Session = Depends(get_session),
    _admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[TenantListRow]:
    tenants = session.exec(select(Tenant)).all()
    plans_by_id = {p.id: p for p in session.exec(select(Plan)).all()}
    rows = []
    for tenant in tenants:
        plan = plans_by_id.get(tenant.active_plan_id) if tenant.active_plan_id else None
        subscription = get_current_subscription(session, tenant.id)

        def _limit_or_none(code: str) -> int | None:
            try:
                return get_limit(session, tenant.id, code)
            except ValueError:
                return None

        rows.append(
            TenantListRow(
                id=tenant.id,
                company_name=tenant.company_name,
                tenant_code=tenant.tenant_code,
                plan_code=plan.code if plan else None,
                users_used=get_usage(session, tenant.id, "MAX_USERS"),
                users_max=_limit_or_none("MAX_USERS"),
                skus_used=get_usage(session, tenant.id, "MAX_SKUS"),
                skus_max=_limit_or_none("MAX_SKUS"),
                subscription_status=subscription.status.value if subscription else None,
                amc_renewal_date=subscription.renewal_date if subscription else None,
                tenant_status=tenant.status.value,
            )
        )
    return rows


@router.get("/upgrade-requests", response_model=list[UpgradeRequestAdminRow])
async def list_upgrade_requests(
    include_decided: bool = False,
    session: Session = Depends(get_session),
    _admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[UpgradeRequestAdminRow]:
    """Cross-tenant view of upgrade requests — before this existed, a
    request only ever surfaced if an admin happened to open that exact
    tenant and change its plan. Defaults to pending only; pass
    `include_decided=true` for the full history."""
    query = select(UpgradeRequest).order_by(UpgradeRequest.requested_at.desc())
    if not include_decided:
        query = query.where(UpgradeRequest.status == UpgradeRequestStatus.pending)
    requests = session.exec(query).all()

    tenants_by_id = {t.id: t for t in session.exec(select(Tenant)).all()}
    plans_by_id = {p.id: p for p in session.exec(select(Plan)).all()}

    rows = []
    for req in requests:
        tenant = tenants_by_id.get(req.tenant_id)
        if tenant is None:
            continue
        plan = plans_by_id.get(req.requested_plan_id)

        # `users` is RLS-protected (Section 11.2) — same workaround as
        # get_tenant_detail, applied once per request's own tenant since
        # this list spans many tenants.
        set_rls_tenant(session, tenant.id)
        requester = session.get(User, req.requested_by)

        rows.append(
            UpgradeRequestAdminRow(
                id=req.id,
                tenant_id=tenant.id,
                tenant_code=tenant.tenant_code,
                company_name=tenant.company_name,
                requested_plan_code=plan.code if plan else "unknown",
                requested_by_username=requester.username if requester else None,
                note=req.note,
                status=req.status.value,
                requested_at=req.requested_at,
            )
        )
    return rows


@router.post("/upgrade-requests/{request_id}/approve", response_model=TenantDetail)
async def approve_upgrade_request(
    request_id: uuid.UUID,
    payload: ApproveUpgradeRequestRequest,
    session: Session = Depends(get_session),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantDetail:
    """Approving is just `change_plan` to the requested plan — delegates
    entirely so the downgrade-impact check, audit trail, and "mark matching
    pending requests approved" logic all stay in one place."""
    req = session.get(UpgradeRequest, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="upgrade request not found")
    if req.status != UpgradeRequestStatus.pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="upgrade request is not pending")

    plan = session.get(Plan, req.requested_plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="requested plan no longer exists")

    change_payload = ChangePlanRequest(plan_code=plan.code, reason=payload.reason, confirm=payload.confirm)
    return await change_plan(req.tenant_id, change_payload, session=session, admin=admin)


@router.post("/upgrade-requests/{request_id}/reject", response_model=UpgradeRequestAdminRow)
async def reject_upgrade_request(
    request_id: uuid.UUID,
    payload: RejectUpgradeRequestRequest,
    session: Session = Depends(get_session),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> UpgradeRequestAdminRow:
    req = session.get(UpgradeRequest, request_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="upgrade request not found")
    if req.status != UpgradeRequestStatus.pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="upgrade request is not pending")

    tenant = _get_tenant_or_404(session, req.tenant_id)
    plan = session.get(Plan, req.requested_plan_id)

    req.status = UpgradeRequestStatus.rejected
    req.decided_by = admin.id
    req.decided_at = datetime.now(timezone.utc)
    session.add(req)

    record_audit(
        session,
        platform_admin_id=admin.id,
        action="REJECT_UPGRADE_REQUEST",
        tenant_id=tenant.id,
        old_value={"status": "pending"},
        new_value={"status": "rejected", "requested_plan_code": plan.code if plan else None},
        reason=payload.reason,
    )
    session.commit()
    session.refresh(req)

    set_rls_tenant(session, tenant.id)
    requester = session.get(User, req.requested_by)

    return UpgradeRequestAdminRow(
        id=req.id,
        tenant_id=tenant.id,
        tenant_code=tenant.tenant_code,
        company_name=tenant.company_name,
        requested_plan_code=plan.code if plan else "unknown",
        requested_by_username=requester.username if requester else None,
        note=req.note,
        status=req.status.value,
        requested_at=req.requested_at,
    )


@router.get("/tenants/{tenant_id}", response_model=TenantDetail)
async def get_tenant_detail(
    tenant_id: uuid.UUID,
    session: Session = Depends(get_session),
    _admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantDetail:
    tenant = _get_tenant_or_404(session, tenant_id)
    plan = session.get(Plan, tenant.active_plan_id) if tenant.active_plan_id else None
    subscription = get_current_subscription(session, tenant.id)

    features = {f.code: can_use_feature(session, tenant.id, f.code) for f in session.exec(select(Feature)).all()}

    limits: dict[str, dict[str, int]] = {}
    for code in PLAN_LIMITS:
        try:
            limits[code] = {"used": get_usage(session, tenant.id, code), "max": get_limit(session, tenant.id, code)}
        except ValueError:
            continue

    # `users` is RLS-protected (Section 11.2) — set the session var for
    # *this* tenant so the query returns rows under a real (non-superuser)
    # production DB role too, not just under this repo's superuser dev
    # role where RLS happens to be inert. See this module's docstring.
    set_rls_tenant(session, tenant.id)
    users = session.exec(select(User).where(User.tenant_id == tenant.id)).all()

    return TenantDetail(
        id=tenant.id,
        company_name=tenant.company_name,
        tenant_code=tenant.tenant_code,
        tenant_status=tenant.status.value,
        plan_code=plan.code if plan else None,
        plan_name=plan.name if plan else None,
        features=features,
        limits=limits,
        subscription_status=subscription.status.value if subscription else None,
        subscription_start_date=subscription.start_date if subscription else None,
        subscription_renewal_date=subscription.renewal_date if subscription else None,
        annual_amc=str(subscription.annual_amc) if subscription else None,
        users=[TenantUserRow(id=u.id, username=u.username, role=u.role.value, is_active=u.is_active) for u in users],
    )


@router.get("/tenants/{tenant_id}/plan-change-impact", response_model=PlanChangeImpact)
async def get_plan_change_impact(
    tenant_id: uuid.UUID,
    target_plan_code: str,
    session: Session = Depends(get_session),
    _admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> PlanChangeImpact:
    """CLAUDE.md Stage 13's downgrade-impact check, as its own read-only
    endpoint — call this before `change-plan` to show an operator what
    would actually happen. Changes nothing."""
    tenant = _get_tenant_or_404(session, tenant_id)
    target_plan = session.exec(select(Plan).where(Plan.code == target_plan_code)).first()
    if target_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="plan not found")
    return PlanChangeImpact(**assess_plan_change_impact(session, tenant, target_plan))


@router.post("/tenants/{tenant_id}/change-plan", response_model=TenantDetail)
async def change_plan(
    tenant_id: uuid.UUID,
    payload: ChangePlanRequest,
    session: Session = Depends(get_session),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantDetail:
    """Upgrading only unlocks features/limits — no business data is
    touched. Downgrading below current usage is allowed too (data is never
    deleted): `check_limit` naturally blocks *new* creates once usage
    exceeds the new plan's cap, which is exactly CLAUDE.md's "preserve
    data, prevent new creation" downgrade behavior, for free.

    Stage 13's downgrade-impact check gates this: if
    `assess_plan_change_impact` finds anything (exceeded limits, features
    that would be lost), this call is refused with 409 unless
    `payload.confirm` is true — an operator must have seen the impact
    (`GET .../plan-change-impact`) and explicitly accepted it, not just
    click through a plan dropdown."""
    tenant = _get_tenant_or_404(session, tenant_id)
    new_plan = session.exec(select(Plan).where(Plan.code == payload.plan_code)).first()
    if new_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="plan not found")

    impact = assess_plan_change_impact(session, tenant, new_plan)
    if (impact["exceeded_limits"] or impact["lost_features"]) and not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PLAN_CHANGE_IMPACT_REQUIRES_CONFIRMATION", "impact": impact},
        )

    old_plan = session.get(Plan, tenant.active_plan_id) if tenant.active_plan_id else None
    tenant.active_plan_id = new_plan.id
    session.add(tenant)

    # the recurring AMC is tied to the *current* plan and must track a plan
    # change — `ensure_subscription` only sets it once, at first creation,
    # so without this a tenant's displayed AMC stays frozen at whatever
    # plan they started on forever (e.g. always showing Essential's
    # ₹90,000 after upgrading to Enterprise). `setup_fee` is a one-time
    # historical charge and deliberately left untouched.
    current_subscription = get_current_subscription(session, tenant.id)
    if current_subscription is not None:
        current_subscription.annual_amc = new_plan.annual_amc
        session.add(current_subscription)

    # close out any pending upgrade request that targeted this plan —
    # closes the loop from Stage 10's "Request Upgrade" without requiring
    # a separate approve-request action for the common case.
    pending = session.exec(
        select(UpgradeRequest).where(
            UpgradeRequest.tenant_id == tenant.id,
            UpgradeRequest.requested_plan_id == new_plan.id,
            UpgradeRequest.status == UpgradeRequestStatus.pending,
        )
    ).all()
    for req in pending:
        req.status = UpgradeRequestStatus.approved
        req.decided_by = admin.id
        req.decided_at = datetime.now(timezone.utc)
        session.add(req)

    new_value: dict = {"plan_code": new_plan.code}
    if impact["exceeded_limits"] or impact["lost_features"]:
        new_value["confirmed_impact"] = impact  # operator explicitly accepted this — keep it on the record

    record_audit(
        session,
        platform_admin_id=admin.id,
        action="CHANGE_PLAN",
        tenant_id=tenant.id,
        old_value={"plan_code": old_plan.code if old_plan else None},
        new_value=new_value,
        reason=payload.reason,
    )
    session.commit()
    return await get_tenant_detail(tenant_id, session=session, _admin=admin)


@router.post("/tenants/{tenant_id}/revoke-plan", response_model=TenantDetail)
async def revoke_plan(
    tenant_id: uuid.UUID,
    payload: RevokePlanRequest,
    session: Session = Depends(get_session),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantDetail:
    """Clears `Tenant.active_plan_id` entirely — distinct from `suspend`
    (which blocks login outright). A revoked tenant can still log in, but
    `can_use_feature`/`check_limit` fail closed for everything not covered
    by a `TenantFeatureOverride`/`TenantLimitOverride` (see entitlements.py
    and usage_limits.py's `NO_ACTIVE_PLAN` handling). No business data is
    touched — the same "never delete, only restrict new access" principle
    as a downgrade."""
    tenant = _get_tenant_or_404(session, tenant_id)
    old_plan = session.get(Plan, tenant.active_plan_id) if tenant.active_plan_id else None
    if old_plan is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="tenant already has no active plan")

    tenant.active_plan_id = None
    session.add(tenant)

    record_audit(
        session,
        platform_admin_id=admin.id,
        action="REVOKE_PLAN",
        tenant_id=tenant.id,
        old_value={"plan_code": old_plan.code},
        new_value={"plan_code": None},
        reason=payload.reason,
    )
    session.commit()
    return await get_tenant_detail(tenant_id, session=session, _admin=admin)


@router.post("/tenants/{tenant_id}/feature-overrides", response_model=TenantDetail)
async def override_feature(
    tenant_id: uuid.UUID,
    payload: FeatureOverrideRequest,
    session: Session = Depends(get_session),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantDetail:
    tenant = _get_tenant_or_404(session, tenant_id)
    feature = session.exec(select(Feature).where(Feature.code == payload.feature_code)).first()
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feature not found")

    existing = session.exec(
        select(TenantFeatureOverride).where(
            TenantFeatureOverride.tenant_id == tenant.id, TenantFeatureOverride.feature_id == feature.id
        )
    ).first()
    old_value = {"enabled": existing.enabled} if existing else None

    if existing:
        existing.enabled = payload.enabled
        existing.reason = payload.reason
        existing.approved_by = admin.id
        session.add(existing)
    else:
        session.add(
            TenantFeatureOverride(
                tenant_id=tenant.id,
                feature_id=feature.id,
                enabled=payload.enabled,
                reason=payload.reason,
                approved_by=admin.id,
            )
        )

    record_audit(
        session,
        platform_admin_id=admin.id,
        action="FEATURE_OVERRIDE",
        tenant_id=tenant.id,
        old_value=old_value,
        new_value={"feature_code": feature.code, "enabled": payload.enabled},
        reason=payload.reason,
    )
    session.commit()
    return await get_tenant_detail(tenant_id, session=session, _admin=admin)


@router.post("/tenants/{tenant_id}/limit-overrides", response_model=TenantDetail)
async def override_limit(
    tenant_id: uuid.UUID,
    payload: LimitOverrideRequest,
    session: Session = Depends(get_session),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantDetail:
    tenant = _get_tenant_or_404(session, tenant_id)
    if payload.limit_code not in PLAN_LIMITS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown limit_code")

    existing = session.exec(
        select(TenantLimitOverride).where(
            TenantLimitOverride.tenant_id == tenant.id, TenantLimitOverride.limit_code == payload.limit_code
        )
    ).first()
    old_value = {"override_value": existing.override_value} if existing else None

    if existing:
        existing.override_value = payload.override_value
        existing.reason = payload.reason
        existing.approved_by = admin.id
        session.add(existing)
    else:
        session.add(
            TenantLimitOverride(
                tenant_id=tenant.id,
                limit_code=payload.limit_code,
                override_value=payload.override_value,
                reason=payload.reason,
                approved_by=admin.id,
            )
        )

    record_audit(
        session,
        platform_admin_id=admin.id,
        action="LIMIT_OVERRIDE",
        tenant_id=tenant.id,
        old_value=old_value,
        new_value={"limit_code": payload.limit_code, "override_value": payload.override_value},
        reason=payload.reason,
    )
    session.commit()
    return await get_tenant_detail(tenant_id, session=session, _admin=admin)


@router.post("/tenants/{tenant_id}/suspend", response_model=TenantDetail)
async def suspend_tenant(
    tenant_id: uuid.UUID,
    payload: SuspendRequest,
    session: Session = Depends(get_session),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantDetail:
    tenant = _get_tenant_or_404(session, tenant_id)
    old_status = tenant.status.value
    tenant.status = TenantStatus.suspended
    session.add(tenant)
    record_audit(
        session,
        platform_admin_id=admin.id,
        action="SUSPEND_TENANT",
        tenant_id=tenant.id,
        old_value={"status": old_status},
        new_value={"status": TenantStatus.suspended.value},
        reason=payload.reason,
    )
    session.commit()
    return await get_tenant_detail(tenant_id, session=session, _admin=admin)


@router.post("/tenants/{tenant_id}/reactivate", response_model=TenantDetail)
async def reactivate_tenant(
    tenant_id: uuid.UUID,
    payload: ReactivateRequest,
    session: Session = Depends(get_session),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantDetail:
    tenant = _get_tenant_or_404(session, tenant_id)
    old_status = tenant.status.value
    tenant.status = TenantStatus.active
    session.add(tenant)
    record_audit(
        session,
        platform_admin_id=admin.id,
        action="REACTIVATE_TENANT",
        tenant_id=tenant.id,
        old_value={"status": old_status},
        new_value={"status": TenantStatus.active.value},
        reason=payload.reason,
    )
    session.commit()
    return await get_tenant_detail(tenant_id, session=session, _admin=admin)


@router.post("/tenants/{tenant_id}/extend-subscription", response_model=TenantDetail)
async def extend_subscription(
    tenant_id: uuid.UUID,
    payload: ExtendSubscriptionRequest,
    session: Session = Depends(get_session),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> TenantDetail:
    tenant = _get_tenant_or_404(session, tenant_id)
    subscription = get_current_subscription(session, tenant.id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant has no subscription to extend")

    old_renewal = subscription.renewal_date
    old_status = subscription.status.value
    subscription.renewal_date = payload.new_renewal_date
    subscription.status = SubscriptionStatus.active  # extending clears EXPIRING/GRACE_PERIOD/EXPIRED
    session.add(subscription)
    # if the automatic grace-period cutoff (services/subscription_lifecycle.py)
    # already suspended this tenant, paying the AMC and extending is exactly
    # what should lift that — reactivate() remains the tool for suspensions
    # unrelated to the subscription date (e.g. abuse, manual hold).
    tenant.status = TenantStatus.active
    session.add(tenant)

    record_audit(
        session,
        platform_admin_id=admin.id,
        action="EXTEND_SUBSCRIPTION",
        tenant_id=tenant.id,
        old_value={"renewal_date": str(old_renewal) if old_renewal else None, "status": old_status},
        new_value={"renewal_date": str(payload.new_renewal_date), "status": SubscriptionStatus.active.value},
        reason=payload.reason,
    )
    session.commit()
    return await get_tenant_detail(tenant_id, session=session, _admin=admin)


@router.get("/tenants/{tenant_id}/audit-log", response_model=list[AuditLogEntry])
async def get_tenant_audit_log(
    tenant_id: uuid.UUID,
    session: Session = Depends(get_session),
    _admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> list[AuditLogEntry]:
    _get_tenant_or_404(session, tenant_id)
    entries = session.exec(
        select(PlatformAuditLog)
        .where(PlatformAuditLog.tenant_id == tenant_id)
        .order_by(PlatformAuditLog.created_at.desc())
    ).all()
    admins_by_id = {a.id: a for a in session.exec(select(PlatformAdmin)).all()}
    return [
        AuditLogEntry(
            id=e.id,
            platform_admin_username=admins_by_id[e.platform_admin_id].username
            if e.platform_admin_id in admins_by_id
            else "unknown",
            action=e.action,
            tenant_id=e.tenant_id,
            old_value=e.old_value,
            new_value=e.new_value,
            reason=e.reason,
            created_at=e.created_at,
        )
        for e in entries
    ]
