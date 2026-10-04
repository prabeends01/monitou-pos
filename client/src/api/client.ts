import { fetch } from "@tauri-apps/plugin-http";

import type {
  AttendanceRecord,
  Barcode,
  BarcodeScanResult,
  CurrentStockRow,
  LeaveRequest,
  LowStockAlert,
  PlanChangeImpact,
  PlanComparison,
  PlatformAuditLogEntry,
  PlatformDashboardStats,
  PlatformTenantDetail,
  PlatformTenantListRow,
  PlatformUpgradeRequestRow,
  Product,
  Sale,
  SaleCreatePayload,
  SalesSummaryBucket,
  StaffUser,
  StockMovementResult,
  StockStats,
  TaDaClaim,
  TenantEntitlements,
  UpgradeRequest,
} from "../types";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

/** Thin HTTP wrapper over the FastAPI backend. Screens never call `fetch`
 * directly — see CLAUDE.md Section 4: client-server, not client-database.
 * Every read and write goes straight to the server; there is no local
 * cache or offline queue.
 * Uses `@tauri-apps/plugin-http`'s fetch (proxied through the Rust side) so
 * requests aren't subject to the webview's CORS restrictions. */
export class ApiClient {
  private baseUrl: string;
  token: string | null = null;
  role: string | null = null;
  /** A completely separate credential — never sent on a tenant request, and
   * `token` above is never sent on a platform-admin request (see
   * `platformAdminRequest` below). Mirrors the backend's separate JWT
   * audiences (CLAUDE.md Section 11.9.6/Stage 11): this is a different
   * operator, not an elevated tenant permission. */
  platformAdminToken: string | null = null;
  platformAdminUsername: string | null = null;
  /** Set once from AppContext — fires on any 401, so a stale/invalidated
   * session (e.g. the backend's database was reset, so the token's user id
   * no longer exists) kicks back to the login screen with a clear reason
   * instead of every screen just quietly showing no data. */
  onUnauthorized: ((detail: string) => void) | null = null;
  onPlatformAdminUnauthorized: ((detail: string) => void) | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  private async doFetch(path: string, init: RequestInit, token: string | null): Promise<Response> {
    const headers = new Headers(init.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const resp = await fetch(`${this.baseUrl}${path}`, { ...init, headers });
    if (!resp.ok) {
      let detail = await resp.text();
      try {
        const body = JSON.parse(detail);
        detail = body.detail ?? detail;
      } catch {
        // not JSON, keep raw text
      }
      throw new ApiError(resp.status, typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return resp;
  }

  private async request(path: string, init: RequestInit = {}): Promise<Response> {
    try {
      return await this.doFetch(path, init, this.token);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401 && this.token) {
        this.token = null;
        this.role = null;
        this.onUnauthorized?.(err.detail);
      }
      throw err;
    }
  }

  private async requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
    const resp = await this.request(path, init);
    return (await resp.json()) as T;
  }

  private async platformAdminRequestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
    try {
      const resp = await this.doFetch(path, init, this.platformAdminToken);
      return (await resp.json()) as T;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401 && this.platformAdminToken) {
        this.platformAdminToken = null;
        this.platformAdminUsername = null;
        this.onPlatformAdminUnauthorized?.(err.detail);
      }
      throw err;
    }
  }

  private jsonInit(method: string, body: unknown): RequestInit {
    return {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    };
  }

  async health(): Promise<boolean> {
    try {
      const resp = await fetch(`${this.baseUrl}/health`, { method: "GET" });
      if (!resp.ok) console.warn(`health check: ${this.baseUrl}/health returned ${resp.status}`);
      return resp.ok;
    } catch (err) {
      console.error(`health check failed reaching ${this.baseUrl}/health`, err);
      return false;
    }
  }

  async login(tenantCode: string, username: string, password: string): Promise<string> {
    // client_id carries the tenant/shop code — usernames are unique per
    // tenant, not globally, so the backend needs it to know which tenant's
    // user table to check (see CLAUDE.md Section 11.9b).
    const body = new URLSearchParams({ client_id: tenantCode, username, password });
    const resp = await this.request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });
    const data = (await resp.json()) as { access_token: string; role: string };
    this.token = data.access_token;
    this.role = data.role;
    return data.role;
  }

  /** Live search over barcode value, SKU, and product name — powers POS
   * billing's search-as-you-type dropdown directly against the server. */
  searchProducts(query: string, limit = 8): Promise<BarcodeScanResult[]> {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    return this.requestJson(`/barcodes/search?${params.toString()}`);
  }

  /** Exact barcode lookup — the scanner-gun fast path. */
  getBarcode(value: string): Promise<BarcodeScanResult> {
    return this.requestJson(`/barcodes/${encodeURIComponent(value)}`);
  }

  /** Admin catalog management — gated server-side by BARCODE_GENERATION
   * (Essential+; see BarcodeAdmin.tsx and CLAUDE.md Stage 5/8). */
  createBarcode(payload: {
    product_id: string;
    barcode_value: string;
    pack_qty: number;
    label: string;
  }): Promise<Barcode> {
    return this.requestJson("/barcodes", this.jsonInit("POST", payload));
  }

  createSale(payload: SaleCreatePayload): Promise<Sale> {
    return this.requestJson("/sales", this.jsonInit("POST", payload));
  }

  listSales(): Promise<Sale[]> {
    return this.requestJson("/sales");
  }

  async getInvoicePdf(saleId: string): Promise<ArrayBuffer> {
    const resp = await this.request(`/sales/${saleId}/invoice`);
    return resp.arrayBuffer();
  }

  getProducts(): Promise<Product[]> {
    return this.requestJson("/products");
  }

  createProduct(payload: Record<string, unknown>): Promise<Product> {
    return this.requestJson("/products", this.jsonInit("POST", payload));
  }

  stockAdjustment(payload: Record<string, unknown>): Promise<StockMovementResult> {
    return this.requestJson("/stock/adjustments", this.jsonInit("POST", payload));
  }

  purchaseReceive(payload: Record<string, unknown>): Promise<StockMovementResult> {
    return this.requestJson("/stock/purchases/receive", this.jsonInit("POST", payload));
  }

  stockBalance(productId: string): Promise<{ product_id: string; balance: number }> {
    return this.requestJson(`/stock/balance/${productId}`);
  }

  getCurrentStock(): Promise<CurrentStockRow[]> {
    return this.requestJson("/stock/current");
  }

  async downloadStockCSV(): Promise<void> {
    const resp = await this.request("/stock/current/export");
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "current_stock.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  getUsers(): Promise<StaffUser[]> {
    return this.requestJson("/users");
  }

  listAttendance(workDate: string): Promise<AttendanceRecord[]> {
    const params = new URLSearchParams({ work_date: workDate });
    return this.requestJson(`/hr/attendance?${params.toString()}`);
  }

  markAttendance(payload: Record<string, unknown>): Promise<AttendanceRecord> {
    return this.requestJson("/hr/attendance", this.jsonInit("POST", payload));
  }

  listLeaveRequests(): Promise<LeaveRequest[]> {
    return this.requestJson("/hr/leave");
  }

  createLeaveRequest(payload: Record<string, unknown>): Promise<LeaveRequest> {
    return this.requestJson("/hr/leave", this.jsonInit("POST", payload));
  }

  decideLeaveRequest(id: string, decision: "approve" | "reject"): Promise<LeaveRequest> {
    return this.requestJson(`/hr/leave/${id}/${decision}`, this.jsonInit("POST", {}));
  }

  listTaDaClaims(): Promise<TaDaClaim[]> {
    return this.requestJson("/hr/ta-da");
  }

  createTaDaClaim(payload: Record<string, unknown>): Promise<TaDaClaim> {
    return this.requestJson("/hr/ta-da", this.jsonInit("POST", payload));
  }

  decideTaDaClaim(id: string, decision: "approve" | "reject", amountApproved?: string): Promise<TaDaClaim> {
    const payload = decision === "approve" && amountApproved ? { amount_approved: amountApproved } : {};
    return this.requestJson(`/hr/ta-da/${id}/${decision}`, this.jsonInit("POST", payload));
  }

  markTaDaClaimPaid(id: string): Promise<TaDaClaim> {
    return this.requestJson(`/hr/ta-da/${id}/mark-paid`, this.jsonInit("POST", {}));
  }

  salesSummary(period: string, from: string, to: string): Promise<SalesSummaryBucket[]> {
    const params = new URLSearchParams({ period, from, to });
    return this.requestJson(`/reports/sales-summary?${params.toString()}`);
  }

  stockStats(): Promise<StockStats> {
    return this.requestJson("/reports/stock-stats");
  }

  lowStockAlerts(): Promise<LowStockAlert[]> {
    return this.requestJson("/reports/low-stock-alerts");
  }

  getEntitlements(): Promise<TenantEntitlements> {
    return this.requestJson("/tenant/me/entitlements");
  }

  getPlanComparison(): Promise<PlanComparison> {
    return this.requestJson("/tenant/me/plan-comparison");
  }

  listUpgradeRequests(): Promise<UpgradeRequest[]> {
    return this.requestJson("/tenant/me/upgrade-requests");
  }

  /** Records a request for Platform Admin to review — never changes the
   * tenant's plan directly (CLAUDE.md Stage 10/13). */
  requestUpgrade(requestedPlanCode: string, note?: string): Promise<UpgradeRequest> {
    return this.requestJson(
      "/tenant/me/upgrade-requests",
      this.jsonInit("POST", { requested_plan_code: requestedPlanCode, note: note ?? null }),
    );
  }

  // --- Platform Admin (CLAUDE.md Stage 11) — every method below uses
  // `platformAdminToken`, never `token`, and vice versa for everything
  // above. Never call these without first calling platformAdminLogin(). ---

  async platformAdminLogin(username: string, password: string): Promise<void> {
    const body = new URLSearchParams({ username, password });
    const resp = await this.doFetch(
      "/platform-admin/auth/login",
      { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: body.toString() },
      null,
    );
    const data = (await resp.json()) as { access_token: string };
    this.platformAdminToken = data.access_token;
    this.platformAdminUsername = username;
  }

  platformAdminLogout(): void {
    this.platformAdminToken = null;
    this.platformAdminUsername = null;
  }

  getPlatformDashboard(): Promise<PlatformDashboardStats> {
    return this.platformAdminRequestJson("/platform-admin/dashboard");
  }

  listPlatformTenants(): Promise<PlatformTenantListRow[]> {
    return this.platformAdminRequestJson("/platform-admin/tenants");
  }

  getPlatformTenantDetail(tenantId: string): Promise<PlatformTenantDetail> {
    return this.platformAdminRequestJson(`/platform-admin/tenants/${tenantId}`);
  }

  getPlatformTenantAuditLog(tenantId: string): Promise<PlatformAuditLogEntry[]> {
    return this.platformAdminRequestJson(`/platform-admin/tenants/${tenantId}/audit-log`);
  }

  /** CLAUDE.md Stage 13's downgrade-impact check — call before
   * `changeTenantPlan` so the operator can see what would actually change.
   * Read-only, changes nothing. */
  getPlanChangeImpact(tenantId: string, targetPlanCode: string): Promise<PlanChangeImpact> {
    const params = new URLSearchParams({ target_plan_code: targetPlanCode });
    return this.platformAdminRequestJson(`/platform-admin/tenants/${tenantId}/plan-change-impact?${params}`);
  }

  /** `confirm` must be true if `getPlanChangeImpact` came back non-empty —
   * the backend refuses with 409 otherwise (never silently applies a
   * plan reduction the operator hasn't explicitly acknowledged). */
  changeTenantPlan(
    tenantId: string,
    planCode: string,
    reason: string,
    confirm = false,
  ): Promise<PlatformTenantDetail> {
    return this.platformAdminRequestJson(
      `/platform-admin/tenants/${tenantId}/change-plan`,
      this.jsonInit("POST", { plan_code: planCode, reason, confirm }),
    );
  }

  /** Clears the tenant's plan entirely — distinct from suspend (which
   * blocks login outright). The tenant can still log in, but loses every
   * plan-gated feature (fails closed, same as any tenant with no plan). */
  revokeTenantPlan(tenantId: string, reason: string): Promise<PlatformTenantDetail> {
    return this.platformAdminRequestJson(
      `/platform-admin/tenants/${tenantId}/revoke-plan`,
      this.jsonInit("POST", { reason }),
    );
  }

  overrideTenantFeature(
    tenantId: string,
    featureCode: string,
    enabled: boolean,
    reason: string,
  ): Promise<PlatformTenantDetail> {
    return this.platformAdminRequestJson(
      `/platform-admin/tenants/${tenantId}/feature-overrides`,
      this.jsonInit("POST", { feature_code: featureCode, enabled, reason }),
    );
  }

  overrideTenantLimit(
    tenantId: string,
    limitCode: string,
    overrideValue: number,
    reason: string,
  ): Promise<PlatformTenantDetail> {
    return this.platformAdminRequestJson(
      `/platform-admin/tenants/${tenantId}/limit-overrides`,
      this.jsonInit("POST", { limit_code: limitCode, override_value: overrideValue, reason }),
    );
  }

  suspendTenant(tenantId: string, reason: string): Promise<PlatformTenantDetail> {
    return this.platformAdminRequestJson(
      `/platform-admin/tenants/${tenantId}/suspend`,
      this.jsonInit("POST", { reason }),
    );
  }

  reactivateTenant(tenantId: string, reason: string): Promise<PlatformTenantDetail> {
    return this.platformAdminRequestJson(
      `/platform-admin/tenants/${tenantId}/reactivate`,
      this.jsonInit("POST", { reason }),
    );
  }

  extendTenantSubscription(tenantId: string, newRenewalDate: string, reason: string): Promise<PlatformTenantDetail> {
    return this.platformAdminRequestJson(
      `/platform-admin/tenants/${tenantId}/extend-subscription`,
      this.jsonInit("POST", { new_renewal_date: newRenewalDate, reason }),
    );
  }

  /** Cross-tenant upgrade-request inbox. Defaults to pending only. */
  listPlatformUpgradeRequests(includeDecided = false): Promise<PlatformUpgradeRequestRow[]> {
    const params = new URLSearchParams({ include_decided: String(includeDecided) });
    return this.platformAdminRequestJson(`/platform-admin/upgrade-requests?${params}`);
  }

  /** Approving is just changeTenantPlan under the hood server-side — same
   * downgrade-impact `confirm` gate applies. */
  approveUpgradeRequest(requestId: string, reason: string, confirm = false): Promise<PlatformTenantDetail> {
    return this.platformAdminRequestJson(
      `/platform-admin/upgrade-requests/${requestId}/approve`,
      this.jsonInit("POST", { reason, confirm }),
    );
  }

  rejectUpgradeRequest(requestId: string, reason: string): Promise<PlatformUpgradeRequestRow> {
    return this.platformAdminRequestJson(
      `/platform-admin/upgrade-requests/${requestId}/reject`,
      this.jsonInit("POST", { reason }),
    );
  }
}
