import uuid
from datetime import datetime, timezone

from sqlmodel import Session, func, select

from app.models.stock_movement import MovementType, StockMovement
from app.tenancy import get_tenant_owned


def get_balance(session: Session, tenant_id: uuid.UUID, product_id: uuid.UUID) -> int:
    total = session.exec(
        select(func.sum(StockMovement.qty_base_units)).where(
            StockMovement.tenant_id == tenant_id, StockMovement.product_id == product_id
        )
    ).one()
    return total or 0


def get_all_balances(session: Session, tenant_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """Balance per product for the whole tenant in one grouped query, for the
    Current Stock view — avoids an N+1 of `get_balance` per product."""
    rows = session.exec(
        select(StockMovement.product_id, func.sum(StockMovement.qty_base_units))
        .where(StockMovement.tenant_id == tenant_id)
        .group_by(StockMovement.product_id)
    ).all()
    return {product_id: total or 0 for product_id, total in rows}


def record_movement(
    session: Session,
    *,
    id: uuid.UUID,
    tenant_id: uuid.UUID,
    product_id: uuid.UUID,
    qty_base_units: int,
    movement_type: MovementType,
    terminal_id: str,
    reference_id: uuid.UUID | None = None,
    created_at_client: datetime | None = None,
    commit: bool = True,
) -> tuple[StockMovement, bool]:
    """Append a movement to the ledger, idempotent by `id`.

    With `commit=False`, the row is only added/flushed so the caller can batch
    it into a larger transaction (e.g. a sale's items) and commit once.

    Returns (movement, went_negative) — went_negative is True if the product's
    balance is below zero after this write, so callers can flag it for admin
    review (offline terminals can independently oversell the same last unit).

    Callers are responsible for having already verified `product_id` belongs
    to `tenant_id` (e.g. via `tenancy.get_tenant_owned`) — this function
    trusts its caller and only scopes reads/writes by `tenant_id`, it does
    not itself validate the product's ownership.
    """
    # tenant-scoped, not a bare session.get() — a client-supplied idempotency
    # id colliding with another tenant's row must never surface that row's
    # data (product_id, qty, movement_type) here; same pattern as
    # services/sales.py's identical idempotency check for `Sale`.
    existing = get_tenant_owned(session, StockMovement, id, tenant_id)
    if existing is not None:
        return existing, get_balance(session, tenant_id, product_id) < 0

    movement = StockMovement(
        id=id,
        tenant_id=tenant_id,
        product_id=product_id,
        qty_base_units=qty_base_units,
        movement_type=movement_type,
        reference_id=reference_id,
        terminal_id=terminal_id,
        created_at_client=created_at_client or datetime.now(timezone.utc),
        synced_at=datetime.now(timezone.utc),
    )
    session.add(movement)
    if commit:
        session.commit()
        session.refresh(movement)
    else:
        session.flush()

    went_negative = get_balance(session, tenant_id, product_id) < 0
    return movement, went_negative
