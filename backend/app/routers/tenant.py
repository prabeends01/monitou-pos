from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_role
from app.db import get_session
from app.models.plan import Feature, Plan
from app.models.tenant import Tenant
from app.models.upgrade_request import UpgradeRequest
from app.models.user import User, UserRole
from app.plan_catalog import PLAN_LIMITS
from app.schemas.plan_comparison import PlanComparisonResponse, UpgradeRequestCreate, UpgradeRequestRead
from app.schemas.tenant import FeatureInfo, LimitUsage, SubscriptionInfo, TenantEntitlementsResponse
from app.services.entitlements import can_use_feature, describe_feature
from app.services.plan_comparison import build_plan_comparison
from app.services.subscriptions import get_current_subscription
from app.services.usage_limits import get_limit, get_usage
from app.tenancy import tenant_scoped

router = APIRouter(prefix="/tenant", tags=["tenant"])


@router.get("/me/entitlements", response_model=TenantEntitlementsResponse)
async def get_my_entitlements(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> TenantEntitlementsResponse:
    tenant = session.get(Tenant, user.tenant_id)
    assert tenant is not None  # get_current_user already validated this tenant exists

    plan = session.get(Plan, tenant.active_plan_id) if tenant.active_plan_id else None

    all_features = session.exec(select(Feature)).all()
    features = {feature.code: can_use_feature(session, tenant.id, feature.code) for feature in all_features}
    feature_info = {feature.code: FeatureInfo(**describe_feature(session, feature.code)) for feature in all_features}

    limits: dict[str, LimitUsage] = {}
    for limit_code in PLAN_LIMITS:
        try:
            limits[limit_code] = LimitUsage(
                used=get_usage(session, tenant.id, limit_code),
                max=get_limit(session, tenant.id, limit_code),
            )
        except ValueError:
            continue  # unresolvable for this tenant (e.g. no active plan) — omit rather than 500

    subscription = get_current_subscription(session, tenant.id)
    subscription_info = (
        SubscriptionInfo(
            status=subscription.status.value,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            renewal_date=subscription.renewal_date,
            setup_fee=str(subscription.setup_fee),
            annual_amc=str(subscription.annual_amc),
        )
        if subscription
        else None
    )

    return TenantEntitlementsResponse(
        tenant_code=tenant.tenant_code,
        company_name=tenant.company_name,
        plan_code=plan.code if plan else None,
        plan_name=plan.name if plan else None,
        tenant_status=tenant.status.value,
        subscription=subscription_info,
        features=features,
        feature_info=feature_info,
        limits=limits,
    )


@router.get("/me/plan-comparison", response_model=PlanComparisonResponse)
async def get_plan_comparison(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> PlanComparisonResponse:
    return build_plan_comparison(session, user.tenant_id)


@router.post("/me/upgrade-requests", response_model=UpgradeRequestRead, status_code=status.HTTP_201_CREATED)
async def create_upgrade_request(
    payload: UpgradeRequestCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
) -> UpgradeRequest:
    """Records a request for Platform Admin to review (Stage 11+) — never
    changes `Tenant.active_plan_id` directly. See CLAUDE.md's Upgrade
    Comparison Screen section: "Upgrade action should generate an upgrade
    request rather than automatically changing the plan.\""""
    plan = session.exec(select(Plan).where(Plan.code == payload.requested_plan_code)).first()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="plan not found")

    tenant = session.get(Tenant, admin.tenant_id)
    if tenant and tenant.active_plan_id == plan.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="tenant is already on this plan")

    request = UpgradeRequest(
        tenant_id=admin.tenant_id,
        requested_plan_id=plan.id,
        requested_by=admin.id,
        note=payload.note,
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return UpgradeRequestRead(
        id=request.id,
        requested_plan_code=plan.code,
        status=request.status.value,
        note=request.note,
        requested_at=request.requested_at,
    )


@router.get("/me/upgrade-requests", response_model=list[UpgradeRequestRead])
async def list_upgrade_requests(
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
) -> list[UpgradeRequestRead]:
    requests = session.exec(
        tenant_scoped(UpgradeRequest, admin.tenant_id).order_by(UpgradeRequest.requested_at.desc())
    ).all()
    plans_by_id = {plan.id: plan for plan in session.exec(select(Plan)).all()}
    return [
        UpgradeRequestRead(
            id=r.id,
            requested_plan_code=plans_by_id[r.requested_plan_id].code,
            status=r.status.value,
            note=r.note,
            requested_at=r.requested_at,
        )
        for r in requests
    ]
