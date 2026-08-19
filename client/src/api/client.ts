import { fetch } from "@tauri-apps/plugin-http";

import type {
  BarcodeScanResult,
  LowStockAlert,
  Product,
  Sale,
  SaleCreatePayload,
  SalesSummaryBucket,
  StockMovementResult,
  StockStats,
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
  /** Set once from AppContext — fires on any 401, so a stale/invalidated
   * session (e.g. the backend's database was reset, so the token's user id
   * no longer exists) kicks back to the login screen with a clear reason
   * instead of every screen just quietly showing no data. */
  onUnauthorized: ((detail: string) => void) | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  private async request(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    if (this.token) headers.set("Authorization", `Bearer ${this.token}`);

    const resp = await fetch(`${this.baseUrl}${path}`, { ...init, headers });
    if (!resp.ok) {
      let detail = await resp.text();
      try {
        const body = JSON.parse(detail);
        detail = body.detail ?? detail;
      } catch {
        // not JSON, keep raw text
      }
      if (resp.status === 401 && this.token) {
        this.token = null;
        this.role = null;
        this.onUnauthorized?.(detail);
      }
      throw new ApiError(resp.status, detail);
    }
    return resp;
  }

  private async requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
    const resp = await this.request(path, init);
    return (await resp.json()) as T;
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

  async login(username: string, password: string): Promise<string> {
    const body = new URLSearchParams({ username, password });
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
}
