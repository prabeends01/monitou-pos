from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.auth.deps import require_role
from app.db import get_session
from app.models.user import User, UserRole
from app.schemas.reports import LowStockAlert, SalesSummaryBucket, StockStats
from app.services.reports import Period, low_stock_products, sales_summary, stock_stats

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/sales-summary", response_model=list[SalesSummaryBucket])
async def get_sales_summary(
    period: Period = Query("daily"),
    from_: datetime = Query(..., alias="from"),
    to: datetime = Query(...),
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role(UserRole.admin)),
) -> list[SalesSummaryBucket]:
    return sales_summary(session, period=period, from_=from_, to=to)


@router.get("/stock-stats", response_model=StockStats)
async def get_stock_stats(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role(UserRole.admin)),
) -> StockStats:
    return stock_stats(session)


@router.get("/low-stock-alerts", response_model=list[LowStockAlert])
async def get_low_stock_alerts(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role(UserRole.admin)),
) -> list[LowStockAlert]:
    return low_stock_products(session)
