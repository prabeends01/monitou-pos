import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TopProduct(BaseModel):
    product_id: uuid.UUID
    sku: str
    name: str
    qty_sold: int
    revenue: Decimal


class SalesSummaryBucket(BaseModel):
    period_start: datetime
    total_sales: Decimal
    total_gst: Decimal
    invoice_count: int
    top_products: list[TopProduct]


class StockMoverEntry(BaseModel):
    product_id: uuid.UUID
    sku: str
    name: str
    qty_sold_30d: int


class StockStats(BaseModel):
    total_skus: int
    total_stock_value: Decimal
    out_of_stock_count: int
    below_threshold_count: int
    fastest_moving: list[StockMoverEntry]
    slowest_moving: list[StockMoverEntry]


class LowStockAlert(BaseModel):
    product_id: uuid.UUID
    sku: str
    name: str
    balance: int
    reorder_threshold: int
    deficit: int
