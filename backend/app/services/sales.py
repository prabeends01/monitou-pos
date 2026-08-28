import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.barcode import Barcode
from app.models.customer import Customer
from app.models.product import Product
from app.models.sale import Sale, SaleItem
from app.models.stock_movement import MovementType
from app.schemas.sale import SaleCreate
from app.services.stock_ledger import record_movement
from app.tenancy import get_tenant_owned

_MAX_INVOICE_NUMBER_ATTEMPTS = 3


def _next_invoice_number(session: Session, tenant_id: uuid.UUID, series: str) -> str:
    """Next sequential number for `series` — max existing numeric suffix + 1,
    starting at 1001. Full-series scan; fine at this app's scale (a spare
    parts shop's invoice volume), see CLAUDE.md's stated no-premature-
    optimization approach for similar low-volume queries."""
    prefix = f"{series}-"
    existing = session.exec(
        select(Sale.invoice_number).where(Sale.tenant_id == tenant_id, Sale.invoice_series == series)
    ).all()
    max_seq = 1000
    for invoice_number in existing:
        suffix = invoice_number.removeprefix(prefix)
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1}"


def create_sale(session: Session, payload: SaleCreate, *, tenant_id: uuid.UUID, cashier_id: uuid.UUID) -> Sale:
    """Write a sale, its line items, and matching stock_movements (sale type)
    in one transaction, all scoped to `tenant_id`. Idempotent by `payload.id`
    — a retried request with the same sale is a no-op, not a double-counted
    sale.

    Each item's `qty_base_units` is the final, client-authoritative quantity
    (see SaleItemCreate) — not re-derived from the barcode's `pack_qty`, so a
    cashier can sell a partial quantity from an opened box.

    If `payload.invoice_number` is omitted, the server assigns the next
    sequential number for `payload.invoice_series` (see `_next_invoice_number`),
    retrying on the rare chance of a concurrent collision.
    """
    existing = get_tenant_owned(session, Sale, payload.id, tenant_id)
    if existing is not None:
        return existing

    if not payload.items:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="sale must have items")

    if payload.customer_id is not None and get_tenant_owned(session, Customer, payload.customer_id, tenant_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"customer {payload.customer_id} not found")

    total_amount = Decimal("0")
    sale_items: list[SaleItem] = []

    for item in payload.items:
        product = get_tenant_owned(session, Product, item.product_id, tenant_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"product {item.product_id} not found")

        if item.barcode_id is not None:
            barcode = get_tenant_owned(session, Barcode, item.barcode_id, tenant_id)
            if barcode is None or barcode.product_id != item.product_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"barcode {item.barcode_id} does not match product {item.product_id}",
                )

        if item.qty_base_units <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="qty_base_units must be positive",
            )

        qty_base_units = item.qty_base_units
        total_amount += item.unit_price * qty_base_units

        sale_items.append(
            SaleItem(
                id=item.id,
                tenant_id=tenant_id,
                sale_id=payload.id,
                product_id=item.product_id,
                barcode_id=item.barcode_id,
                qty_base_units=qty_base_units,
                unit_price=item.unit_price,
            )
        )

    auto_assign = payload.invoice_number is None
    attempts = _MAX_INVOICE_NUMBER_ATTEMPTS if auto_assign else 1

    for attempt in range(1, attempts + 1):
        invoice_number = (
            _next_invoice_number(session, tenant_id, payload.invoice_series)
            if auto_assign
            else payload.invoice_number
        )

        sale = Sale(
            id=payload.id,
            tenant_id=tenant_id,
            invoice_number=invoice_number,
            invoice_series=payload.invoice_series,
            customer_id=payload.customer_id,
            cashier_id=cashier_id,
            terminal_id=payload.terminal_id,
            total_amount=total_amount,
            gst_amount=payload.gst_amount,
            payment_mode=payload.payment_mode,
            created_at_client=payload.created_at_client,
            synced_at=datetime.now(timezone.utc),
        )
        session.add(sale)
        session.add_all(sale_items)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            if attempt == attempts:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"invoice_number {invoice_number} already exists",
                ) from None
            continue
        else:
            break

    for sale_item in sale_items:
        record_movement(
            session,
            id=sale_item.id,
            tenant_id=tenant_id,
            product_id=sale_item.product_id,
            qty_base_units=-sale_item.qty_base_units,
            movement_type=MovementType.sale,
            terminal_id=payload.terminal_id,
            reference_id=sale.id,
            created_at_client=payload.created_at_client,
            commit=False,
        )

    session.commit()
    session.refresh(sale)
    return sale
