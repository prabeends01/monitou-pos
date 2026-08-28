import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth.deps import get_current_user, require_role
from app.db import get_session
from app.models.product import Product
from app.models.stock_movement import MovementType
from app.models.user import User, UserRole
from app.schemas.stock import (
    PurchaseReceiveCreate,
    StockAdjustmentCreate,
    StockBalance,
    StockMovementResult,
)
from app.services.entitlements import require_feature
from app.services.stock_ledger import get_balance, record_movement
from app.tenancy import get_tenant_owned

router = APIRouter(prefix="/stock", tags=["stock"])


@router.post("/adjustments", response_model=StockMovementResult, status_code=status.HTTP_201_CREATED)
async def create_adjustment(
    payload: StockAdjustmentCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("STOCK_ADJUSTMENT")),
) -> StockMovementResult:
    if get_tenant_owned(session, Product, payload.product_id, admin.tenant_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    movement, went_negative = record_movement(
        session,
        id=payload.id,
        tenant_id=admin.tenant_id,
        product_id=payload.product_id,
        qty_base_units=payload.qty_base_units,
        movement_type=MovementType.adjustment,
        terminal_id=payload.terminal_id,
    )
    return StockMovementResult(
        id=movement.id,
        product_id=movement.product_id,
        qty_base_units=movement.qty_base_units,
        movement_type=movement.movement_type.value,
        balance_after=get_balance(session, admin.tenant_id, movement.product_id),
        went_negative=went_negative,
    )


@router.post("/purchases/receive", response_model=StockMovementResult, status_code=status.HTTP_201_CREATED)
async def receive_purchase(
    payload: PurchaseReceiveCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("GRN")),
) -> StockMovementResult:
    if payload.qty_base_units <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="qty_base_units must be positive for a purchase receipt",
        )
    if get_tenant_owned(session, Product, payload.product_id, admin.tenant_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    movement, went_negative = record_movement(
        session,
        id=payload.id,
        tenant_id=admin.tenant_id,
        product_id=payload.product_id,
        qty_base_units=payload.qty_base_units,
        movement_type=MovementType.purchase,
        terminal_id=payload.terminal_id,
        reference_id=payload.reference_id,
    )
    return StockMovementResult(
        id=movement.id,
        product_id=movement.product_id,
        qty_base_units=movement.qty_base_units,
        movement_type=movement.movement_type.value,
        balance_after=get_balance(session, admin.tenant_id, movement.product_id),
        went_negative=went_negative,
    )


@router.get("/balance/{product_id}", response_model=StockBalance)
async def read_balance(
    product_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    _feature: None = Depends(require_feature("STOCK_LEDGER")),
) -> StockBalance:
    if get_tenant_owned(session, Product, product_id, user.tenant_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    return StockBalance(product_id=product_id, balance=get_balance(session, user.tenant_id, product_id))
