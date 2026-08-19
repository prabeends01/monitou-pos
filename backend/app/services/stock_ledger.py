import uuid
from datetime import datetime, timezone

from sqlmodel import Session, func, select

from app.models.stock_movement import MovementType, StockMovement


def get_balance(session: Session, product_id: uuid.UUID) -> int:
    total = session.exec(
        select(func.sum(StockMovement.qty_base_units)).where(StockMovement.product_id == product_id)
    ).one()
    return total or 0


def record_movement(
    session: Session,
    *,
    id: uuid.UUID,
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
    """
    existing = session.get(StockMovement, id)
    if existing is not None:
        return existing, get_balance(session, product_id) < 0

    movement = StockMovement(
        id=id,
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

    went_negative = get_balance(session, product_id) < 0
    return movement, went_negative
