from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.auth.deps import require_role
from app.db import get_session
from app.models.user import User, UserRole
from app.schemas.reports import LowStockAlert, SalesSummaryBucket, StockStats
from app.services.entitlements import can_use_feature, require_feature
from app.services.reports import Period, low_stock_products, sales_summary, stock_stats

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/sales-summary", response_model=list[SalesSummaryBucket])
async def get_sales_summary(
    period: Period = Query("daily"),
    from_: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("BASIC_REPORTS")),
) -> list[SalesSummaryBucket]:
    return sales_summary(session, tenant_id=admin.tenant_id, period=period, from_=from_, to=to)


@router.get("/stock-stats", response_model=StockStats)
async def get_stock_stats(
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("BASIC_REPORTS")),
) -> StockStats:
    stats = stock_stats(session, tenant_id=admin.tenant_id)
    # FAST_MOVING_ANALYSIS / SLOW_MOVING_ANALYSIS are Essential+ — this
    # endpoint's other fields (stock value, out-of-stock/below-threshold
    # counts) are Basic-tier, so the gate is per-field here rather than a
    # hard 403 for the whole endpoint. Same pattern as ProductRead vs
    # ProductReadPublic hiding cost_price for the sales role — plan-driven
    # instead of role-driven.
    if not can_use_feature(session, admin.tenant_id, "FAST_MOVING_ANALYSIS"):
        stats.fastest_moving = []
    if not can_use_feature(session, admin.tenant_id, "SLOW_MOVING_ANALYSIS"):
        stats.slowest_moving = []
    return stats


@router.get("/low-stock-alerts", response_model=list[LowStockAlert])
async def get_low_stock_alerts(
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("LOW_STOCK_ALERT")),
) -> list[LowStockAlert]:
    return low_stock_products(session, tenant_id=admin.tenant_id)
