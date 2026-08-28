export type Role = "admin" | "sales";

export interface LimitUsage {
  used: number;
  max: number;
}

/** Plan-static info about one feature — same for every tenant. Lets
 * FeatureGate's locked-feature card show "available in Essential and
 * Enterprise plans" without re-deriving plan/feature mappings itself. */
export interface FeatureInfo {
  name: string;
  module: string;
  required_plan: string | null;
  message: string;
}

/** The tenant's current commercial term. `null` for a tenant with no
 * subscription row yet (CLAUDE.md Section 11.8/Stage 9) — screens must
 * handle that, not assume it's always present. */
export interface SubscriptionInfo {
  status: string;
  start_date: string;
  end_date: string | null;
  renewal_date: string | null;
  setup_fee: string;
  annual_amc: string;
}

/** GET /tenant/me/entitlements — the one snapshot useFeature/FeatureGate
 * (see hooks/useEntitlements.ts) read from; nothing else in the frontend
 * re-derives plan logic. `features` covers the full catalog by code. */
export interface TenantEntitlements {
  tenant_code: string;
  company_name: string;
  plan_code: string | null;
  plan_name: string | null;
  tenant_status: string;
  subscription: SubscriptionInfo | null;
  features: Record<string, boolean>;
  feature_info: Record<string, FeatureInfo>;
  limits: Record<string, LimitUsage>;
}

export interface PlanColumn {
  code: string;
  name: string;
  setup_price: string;
  annual_amc: string;
  is_current: boolean;
  is_recommended: boolean;
}

export interface ComparisonFeatureRow {
  code: string;
  name: string;
  module: string;
  enabled_by_plan: Record<string, boolean>;
}

/** GET /tenant/me/plan-comparison — Stage 10's Upgrade Comparison Screen.
 * Plan-static (PlanFeature defaults), unlike TenantEntitlements which also
 * reflects per-tenant overrides. */
export interface PlanComparison {
  plans: PlanColumn[];
  features: ComparisonFeatureRow[];
}

export interface UpgradeRequest {
  id: string;
  requested_plan_code: string;
  status: string;
  note: string | null;
  requested_at: string;
}

// --- Platform Admin (CLAUDE.md Stage 11) — entirely separate credential
// space from everything above; see api/client.ts's platformAdmin* methods
// and stores/platformAdminStore.ts. ---

export interface PlatformDashboardStats {
  total_tenants: number;
  active_tenants: number;
  suspended_accounts: number;
  basic_customers: number;
  essential_customers: number;
  enterprise_customers: number;
  amc_due: number;
  upcoming_renewals: number;
  pending_upgrade_requests: number;
}

/** GET /platform-admin/upgrade-requests — the cross-tenant inbox; without
 * this, a request only ever surfaced if an admin happened to open that
 * exact tenant and change its plan themselves. */
export interface PlatformUpgradeRequestRow {
  id: string;
  tenant_id: string;
  tenant_code: string;
  company_name: string;
  requested_plan_code: string;
  requested_by_username: string | null;
  note: string | null;
  status: string;
  requested_at: string;
}

export interface PlatformTenantListRow {
  id: string;
  company_name: string;
  tenant_code: string;
  plan_code: string | null;
  users_used: number;
  users_max: number | null;
  skus_used: number;
  skus_max: number | null;
  subscription_status: string | null;
  amc_renewal_date: string | null;
  tenant_status: string;
}

export interface PlatformTenantUser {
  id: string;
  username: string;
  role: string;
  is_active: boolean;
}

export interface PlatformTenantDetail {
  id: string;
  company_name: string;
  tenant_code: string;
  tenant_status: string;
  plan_code: string | null;
  plan_name: string | null;
  features: Record<string, boolean>;
  limits: Record<string, { used: number; max: number }>;
  subscription_status: string | null;
  subscription_start_date: string | null;
  subscription_renewal_date: string | null;
  annual_amc: string | null;
  users: PlatformTenantUser[];
}

export interface PlanChangeExceededLimit {
  limit_code: string;
  current_usage: number;
  new_limit: number;
}

export interface PlanChangeLostFeature {
  code: string;
  name: string;
}

/** GET .../plan-change-impact — CLAUDE.md Stage 13's downgrade-impact
 * check. Empty exceeded_limits/lost_features means the change is safe to
 * apply with no confirmation needed. */
export interface PlanChangeImpact {
  target_plan_code: string;
  is_downgrade: boolean;
  exceeded_limits: PlanChangeExceededLimit[];
  lost_features: PlanChangeLostFeature[];
}

export interface PlatformAuditLogEntry {
  id: string;
  platform_admin_username: string;
  action: string;
  tenant_id: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  reason: string | null;
  created_at: string;
}

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
