export type Role = "admin" | "sales";

export interface Product {
  id: string;
  sku: string;
  name: string;
  category: string;
  compatible_models: string | null;
  base_unit: string;
  cost_price?: string; // admin only — absent for sales-role responses
  sale_price: string;
  reorder_threshold: number;
  is_active: boolean;
  updated_at: string;
}

export interface Barcode {
  id: string;
  product_id: string;
  barcode_value: string;
  pack_qty: number;
  label: string;
  updated_at: string;
}

export interface SaleItem {
  id: string;
  product_id: string;
  barcode_id: string | null;
  qty_base_units: number;
  unit_price: string;
}

export interface Sale {
  id: string;
  invoice_number: string;
  invoice_series: string;
  customer_id: string | null;
  cashier_id: string;
  terminal_id: string;
  total_amount: string;
  gst_amount: string;
  payment_mode: string;
  created_at_client: string;
  synced_at: string | null;
  items: SaleItem[];
}

/** POST /sales body. `invoice_number` is optional — the server assigns the
 * next sequential number for `invoice_series` when omitted. */
export interface SaleCreatePayload {
  id: string;
  invoice_number?: string;
  invoice_series: string;
  terminal_id: string;
  customer_id: string | null;
  payment_mode: string;
  gst_amount: string;
  created_at_client: string;
  items: {
    id: string;
    product_id: string;
    barcode_id: string | null;
    qty_base_units: number;
    unit_price: string;
  }[];
}

/** What GET /barcodes/{value} and GET /barcodes/search resolve to — a
 * barcode joined with its product, everything the POS cart needs. */
export interface BarcodeScanResult {
  barcode: Barcode;
  product_id: string;
  product_sku: string;
  product_name: string;
  base_units_per_scan: number;
  sale_price: string;
}

export interface TopProduct {
  product_id: string;
  sku: string;
  name: string;
  qty_sold: number;
  revenue: string;
}

export interface SalesSummaryBucket {
  period_start: string;
  total_sales: string;
  total_gst: string;
  invoice_count: number;
  top_products: TopProduct[];
}

export interface StockMoverEntry {
  product_id: string;
  sku: string;
  name: string;
  qty_sold_30d: number;
}

export interface StockStats {
  total_skus: number;
  total_stock_value: string;
  out_of_stock_count: number;
  below_threshold_count: number;
  fastest_moving: StockMoverEntry[];
  slowest_moving: StockMoverEntry[];
}

export interface LowStockAlert {
  product_id: string;
  sku: string;
  name: string;
  balance: number;
  reorder_threshold: number;
  deficit: number;
}

export interface StockMovementResult {
  id: string;
  product_id: string;
  qty_base_units: number;
  movement_type: string;
  balance_after: number;
  went_negative: boolean;
}
