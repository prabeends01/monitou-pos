import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from sqlmodel import Session, select

from app.models.product import Product
from app.models.sale import Sale, SaleItem
from app.schemas.reports import LowStockAlert, SalesSummaryBucket, StockMoverEntry, StockStats, TopProduct
from app.services.stock_ledger import get_balance
from app.tenancy import tenant_scoped

Period = Literal["daily", "weekly", "monthly"]


def _bucket_start(dt: datetime, period: Period) -> datetime:
    dt = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if period == "daily":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "weekly":
        start_of_day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_of_day - timedelta(days=start_of_day.weekday())  # Monday, ISO week start
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def sales_summary(
    session: Session, *, tenant_id: uuid.UUID, period: Period, from_: datetime, to: datetime
) -> list[SalesSummaryBucket]:
    sales = session.exec(
        tenant_scoped(Sale, tenant_id).where(Sale.created_at_client >= from_, Sale.created_at_client <= to)
    ).all()

    buckets: dict[datetime, list[Sale]] = defaultdict(list)
    for sale in sales:
        buckets[_bucket_start(sale.created_at_client, period)].append(sale)

    result: list[SalesSummaryBucket] = []
    for bucket_start in sorted(buckets):
        bucket_sales = buckets[bucket_start]
        sale_ids = [s.id for s in bucket_sales]
        items = session.exec(
            select(SaleItem).where(SaleItem.tenant_id == tenant_id, SaleItem.sale_id.in_(sale_ids))
        ).all()

        per_product: dict[uuid.UUID, dict] = defaultdict(lambda: {"qty": 0, "revenue": Decimal("0")})
        for item in items:
            per_product[item.product_id]["qty"] += item.qty_base_units
            per_product[item.product_id]["revenue"] += item.unit_price * item.qty_base_units

        top_products: list[TopProduct] = []
        for product_id, agg in sorted(per_product.items(), key=lambda kv: kv[1]["revenue"], reverse=True)[:5]:
            product = session.get(Product, product_id)
            top_products.append(
                TopProduct(
                    product_id=product_id,
                    sku=product.sku if product else "",
                    name=product.name if product else "",
                    qty_sold=agg["qty"],
                    revenue=agg["revenue"],
                )
            )

        result.append(
            SalesSummaryBucket(
                period_start=bucket_start,
                total_sales=sum((s.total_amount for s in bucket_sales), Decimal("0")),
                total_gst=sum((s.gst_amount for s in bucket_sales), Decimal("0")),
                invoice_count=len(bucket_sales),
                top_products=top_products,
            )
        )
    return result


def stock_stats(session: Session, *, tenant_id: uuid.UUID) -> StockStats:
    products = session.exec(tenant_scoped(Product, tenant_id)).all()

    total_stock_value = Decimal("0")
    out_of_stock_count = 0
    below_threshold_count = 0
    balances: dict[uuid.UUID, int] = {}

    for product in products:
        balance = get_balance(session, tenant_id, product.id)
        balances[product.id] = balance
        total_stock_value += product.cost_price * balance
        if balance <= 0:
            out_of_stock_count += 1
        if balance <= product.reorder_threshold:
            below_threshold_count += 1

    since = datetime.now(timezone.utc) - timedelta(days=30)
    recent_items = session.exec(
        select(SaleItem, Sale.created_at_client)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.tenant_id == tenant_id, Sale.created_at_client >= since)
    ).all()

    sold_30d: dict[uuid.UUID, int] = defaultdict(int)
    for item, _created_at in recent_items:
        sold_30d[item.product_id] += item.qty_base_units

    def mover_entry(product: Product, qty: int) -> StockMoverEntry:
        return StockMoverEntry(product_id=product.id, sku=product.sku, name=product.name, qty_sold_30d=qty)

    ranked = sorted(products, key=lambda p: sold_30d.get(p.id, 0), reverse=True)
    fastest_moving = [mover_entry(p, sold_30d.get(p.id, 0)) for p in ranked[:5]]
    slowest_moving = [mover_entry(p, sold_30d.get(p.id, 0)) for p in ranked[-5:][::-1]]

    return StockStats(
        total_skus=len(products),
        total_stock_value=total_stock_value,
        out_of_stock_count=out_of_stock_count,
        below_threshold_count=below_threshold_count,
        fastest_moving=fastest_moving,
        slowest_moving=slowest_moving,
    )


def low_stock_products(session: Session, *, tenant_id: uuid.UUID) -> list[LowStockAlert]:
    """Products at or below their reorder_threshold, sorted by how far below.

    Shared by GET /reports/low-stock-alerts and the scheduled digest job —
    keep this the single source of truth for "what counts as low stock".
    """
    products = session.exec(
        tenant_scoped(Product, tenant_id).where(Product.is_active == True)  # noqa: E712
    ).all()

    alerts: list[LowStockAlert] = []
    for product in products:
        balance = get_balance(session, tenant_id, product.id)
        if balance <= product.reorder_threshold:
            alerts.append(
                LowStockAlert(
                    product_id=product.id,
                    sku=product.sku,
                    name=product.name,
                    balance=balance,
                    reorder_threshold=product.reorder_threshold,
                    deficit=product.reorder_threshold - balance,
                )
            )
    alerts.sort(key=lambda a: a.deficit, reverse=True)
    return alerts
