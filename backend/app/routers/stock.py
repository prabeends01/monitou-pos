import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, func, select

from app.auth.deps import get_current_user, require_role
from app.db import get_session
from app.models.product import Product
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
)
from app.models.stock_movement import MovementType
from app.models.user import User, UserRole
from app.schemas.stock import (
    CurrentStockRow,
    PurchaseReceiveCreate,
    StockAdjustmentCreate,
    StockBalance,
    StockMovementResult,
)
from app.services.entitlements import require_feature
from app.services.stock_ledger import get_all_balances, get_balance, record_movement
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


@router.get("/current", response_model=list[CurrentStockRow])
async def read_current_stock(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    _feature: None = Depends(require_feature("STOCK_LEDGER")),
) -> list[CurrentStockRow]:
    products = session.exec(
        select(Product).where(Product.tenant_id == user.tenant_id, Product.is_active).order_by(Product.name)
    ).all()
    balances = get_all_balances(session, user.tenant_id)
    on_order = _get_on_order_qty(session, user.tenant_id)
    rows = []
    for p in products:
        balance = balances.get(p.id, 0)
        on_order_qty = on_order.get(p.id, 0)
        reserved_qty = 0
        rows.append(
            CurrentStockRow(
                product_id=p.id,
                sku=p.sku,
                name=p.name,
                oem_part_number=p.oem_part_number,
                category=p.category,
                subcategory=p.subcategory,
                brand=p.brand,
                base_unit=p.base_unit,
                warehouse=p.warehouse,
                rack=p.rack,
                bin_location=p.bin_location,
                on_hand_qty=balance,
                reserved_qty=reserved_qty,
                available_qty=balance - reserved_qty,
                on_order_qty=on_order_qty,
                reorder_threshold=p.reorder_threshold,
                safety_stock=p.safety_stock,
                max_stock=p.max_stock,
                supplier_name=p.supplier_name,
                supplier_code=p.supplier_code,
                lead_time_days=p.lead_time_days,
                min_order_qty=p.min_order_qty,
                cost_price=p.cost_price,
                sale_price=p.sale_price,
                gst_percent=p.gst_percent,
                critical_part=p.critical_part,
            )
        )
    return rows


def _get_on_order_qty(session: Session, tenant_id: uuid.UUID) -> dict[uuid.UUID, int]:
    pending_statuses = [PurchaseOrderStatus.ordered.value, PurchaseOrderStatus.partially_received.value]
    rows = session.exec(
        select(PurchaseOrderItem.product_id, func.sum(PurchaseOrderItem.qty_base_units))
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
        .where(PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.status.in_(pending_statuses))
        .group_by(PurchaseOrderItem.product_id)
    ).all()
    return {product_id: int(total or 0) for product_id, total in rows}


@router.get("/current/export")
async def export_current_stock(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    _feature: None = Depends(require_feature("STOCK_LEDGER")),
) -> StreamingResponse:
    rows = await read_current_stock(session, user)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "SKU", "Name", "OEM Part Number", "Category", "Subcategory", "Brand", "Unit",
        "Warehouse", "Rack", "Bin Location", "On Hand Qty", "Reserved Qty", "Available Qty",
        "On Order Qty", "Reorder Level", "Safety Stock", "Max Stock", "Preferred Supplier",
        "Supplier Code", "Lead Time Days", "Minimum Order Qty", "Purchase Cost", "Selling Price",
        "GST Percent", "Critical Part",
    ])
    for r in rows:
        writer.writerow([
            r.sku, r.name, r.oem_part_number or "", r.category, r.subcategory or "", r.brand or "",
            r.base_unit, r.warehouse or "", r.rack or "", r.bin_location or "",
            r.on_hand_qty, r.reserved_qty, r.available_qty, r.on_order_qty,
            r.reorder_threshold, r.safety_stock or "", r.max_stock or "",
            r.supplier_name or "", r.supplier_code or "", r.lead_time_days or "",
            r.min_order_qty or "", r.cost_price, r.sale_price, r.gst_percent,
            "Yes" if r.critical_part else "No",
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=current_stock.csv"},
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
