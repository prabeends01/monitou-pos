# CLAUDE.md — Monitou Spare Parts POS & Inventory System

This file is the source of truth for architecture, conventions, and build order.
Read it fully before writing code. Follow the phase order in Section 8 — do not
skip ahead to later phases before earlier ones are working and tested.

---

## 1. Project overview

A retail POS + inventory management system for a shop selling spare parts for
Monitou handling, lifting, and earthmoving equipment.

- **Roles:** `admin` (full access — catalog, stock, users, reports, costs) and
  `sales` (search/scan parts, create sales, print invoices, view own sales
  history only).
- **Client:** Windows desktop app, installed on shop PCs/POS terminals.
- **Backend:** hosted on AWS. The client never talks to the database directly —
  only to the API. There is exactly one database (Postgres) and the client has
  no local database of its own — every read and write goes straight to the
  API in real time. **Decided against offline-first** (this project's
  original design) after repeated, hard-to-debug data-integrity issues from
  a local SQLite cache + outbox + background sync worker; simplicity and one
  source of truth won out over offline capability. The shop PCs are expected
  to have a working network connection to the backend at all times.
- **Barcodes with pack quantities:** many parts (nuts, bolts, washers) are
  bought and sold both as loose pieces and as sealed boxes of 50/100+, each
  with its own barcode. Stock must always resolve to a single base unit count.
- **Compliance:** GST-compliant invoicing (India). Invoice numbers must be
  sequential per series with no gaps — see Section 5.4.

---

## 2. Tech stack

### Backend
- **Python 3.12**, managed with **uv** (not pip/poetry/venv directly)
- **FastAPI** — REST API
- **SQLModel** (SQLAlchemy 2.0 + Pydantic v2) — ORM and request/response schemas
- **Alembic** — migrations
- **PostgreSQL** — the only database, production (AWS RDS) and local dev alike (via `docker compose`, Section 6). No SQLite anywhere in the app (pytest's fixtures use an in-memory SQLite purely for fast, isolated tests — that's test infra, not an application datastore).
- **python-jose** or **PyJWT** — JWT auth
- **passlib[bcrypt]** — password hashing
- **APScheduler** — scheduled jobs (low-stock alerts, daily reports)
- **python-escpos** — thermal receipt printer output
- **weasyprint** or **reportlab** — GST invoice PDFs
- **pytest**, **httpx** — testing

### Windows client
- **Tauri 2.x** (Rust core + WebView2) — lightweight desktop shell; small installer, low RAM use, uses the WebView2 runtime already present on Windows 11/10
- **React 18 + TypeScript** — UI layer
- **Fluent UI v9** (`@fluentui/react-components`) — Microsoft's official Fluent 2 design system, the same visual language native Windows 11 apps use — this is what actually delivers the "looks like a real Windows app" result
- **Vite** — dev server / bundler
- **@tanstack/react-query** — server state, caching, retry logic for API calls
- **Zustand** (or React context, kept minimal) — local UI state (cart, current screen) — UI state only, never server data, never persisted
- **`@tauri-apps/plugin-http`** — every call to the FastAPI backend, direct, no local cache in front of it
- **`@tauri-apps/plugin-store`** — persisted JWT/session only (so the cashier isn't forced to log in every launch); not a data cache
- **Recharts** — sales-summary charts on the admin dashboard
- **Receipt printing:** a small Rust command wrapping the `escpos` crate's `NetworkDriver` (TCP) for ESC/POS thermal printers — working, in production use; PDF-invoice-via-print-dialog remains available as a per-shop choice for printers that don't fit network printing (see `services/invoicing.py` on the backend), not as a contingency for a broken integration
- **Tauri's built-in bundler** — produces the Windows installer (MSI/NSIS) directly, no separate packaging tool needed

### AWS (production)
- **ECS Fargate** running the FastAPI container (start here; can drop to a
  single EC2 instance later if cost matters more than auto-scaling)
- **Application Load Balancer** — HTTPS termination, routes to ECS
- **RDS PostgreSQL** (Multi-AZ)
- **S3** — invoice PDFs, DB export backups
- **Secrets Manager** — DB credentials, JWT signing key
- **Route 53 + ACM** — domain + TLS certificate
- **CloudWatch** — logs and alarms
- **ECR** — container image registry
- **IAM** — task role scoped to only RDS + S3 + Secrets Manager it needs

---

## 3. Repository structure

```
monitou-pos/
├── backend/
│   ├── pyproject.toml          # uv-managed, no requirements.txt
│   ├── uv.lock
│   ├── alembic/
│   │   ├── versions/
│   │   └── env.py
│   ├── app/
│   │   ├── main.py             # FastAPI app entrypoint
│   │   ├── config.py           # settings via pydantic-settings, reads env vars
│   │   ├── db.py                # engine, session dependency
│   │   ├── models/              # SQLModel table models
│   │   │   ├── user.py
│   │   │   ├── product.py
│   │   │   ├── barcode.py
│   │   │   ├── stock_movement.py
│   │   │   ├── supplier.py
│   │   │   ├── purchase_order.py
│   │   │   ├── sale.py
│   │   │   └── customer.py
│   │   ├── schemas/              # Pydantic request/response models
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── products.py
│   │   │   ├── barcodes.py        # includes GET /barcodes/search — the POS search-as-you-type endpoint
│   │   │   ├── stock.py
│   │   │   ├── sales.py
│   │   │   ├── purchases.py
│   │   │   ├── reports.py
│   │   │   └── users.py
│   │   ├── auth/
│   │   │   ├── security.py       # password hashing, JWT issue/verify
│   │   │   └── deps.py           # get_current_user, require_role()
│   │   ├── services/              # business logic, kept out of routers
│   │   │   ├── stock_ledger.py    # stock balance derivation, movement writes
│   │   │   └── invoicing.py       # invoice numbering (server-assigned), GST PDF generation
│   │   └── jobs/
│   │       └── low_stock_alerts.py
│   └── tests/
│       ├── test_auth.py
│       ├── test_products.py
│       ├── test_stock_ledger.py
│       └── test_sales.py
├── client/
│   ├── package.json               # npm/pnpm-managed, not uv — Node project
│   ├── src-tauri/                  # Rust side of Tauri
│   │   ├── Cargo.toml
│   │   ├── tauri.conf.json
│   │   └── src/
│   │       ├── main.rs
│   │       └── printer.rs          # ESC/POS command wrapping the escpos crate
│   └── src/                        # React/TypeScript side
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   └── client.ts           # plugin-http wrapper, attaches JWT — every read/write goes through this, direct to the server
│       ├── screens/
│       │   ├── Login.tsx
│       │   ├── PosBilling.tsx
│       │   ├── ProductAdmin.tsx
│       │   ├── StockAdmin.tsx
│       │   ├── Reports.tsx
│       │   └── Dashboard.tsx       # admin home: sales stats, low-stock alerts, stock stats
│       ├── components/             # shared Fluent UI-based components
│       └── stores/                 # Zustand stores (cart, session)
├── infra/
│   ├── docker/
│   │   ├── Dockerfile.backend
│   │   └── entrypoint.sh           # waits for db, runs migrations, then execs uvicorn
│   ├── ecs/                        # task definitions, service config
│   └── terraform/ (or CDK)         # optional IaC for RDS/ECS/ALB/S3
├── docker-compose.yml               # local dev: postgres + backend, one command
└── CLAUDE.md
```

---

## 4. Architecture summary

- **Client-server, not client-database.** The Windows client (a Tauri app —
  React UI running in the OS's WebView2 engine, wrapped by a thin Rust shell)
  only ever calls the FastAPI REST API over HTTPS. It never has DB
  credentials, and it has no database of its own.
- **Direct to the server, no local cache.** Every screen reads and writes
  straight through `api/client.ts` to the backend — checkout calls
  `POST /sales` synchronously and waits for the result; POS search calls
  `GET /barcodes/search` on the server per keystroke (debounced) instead of
  querying a local copy of the catalog. There is no outbox, no background
  sync worker, and no offline mode: if the network is down, actions fail
  visibly (e.g. checkout shows an error and keeps the cart intact so the
  cashier can retry) rather than queuing silently. **This was a deliberate
  simplification** away from this project's original offline-first design —
  see Section 1.
- **Stock is an append-only ledger, never an edited counter.** Every stock
  change (sale, purchase, adjustment, stock-take, repack) is a new row in
  `stock_movements` with a client-generated unique ID. Current stock = sum of
  movements for that product. The server never overwrites a value, it only
  appends.
- **Idempotent writes.** Every sale/movement carries a UUID generated on the
  client at creation time. The server enforces a unique constraint on that
  ID, so a retried request after a dropped connection (e.g. the client's HTTP
  call times out but the server actually committed it) is a safe no-op, not a
  double-counted sale — this matters even without an offline queue, purely as
  network-retry safety.
- **Negative-balance detection** still exists (`stock_ledger.py` flags any
  product whose computed balance goes negative after a write) as a general
  admin-review safety net — e.g. a bad manual adjustment — not specifically
  an offline-sync concern anymore.
- **Role enforcement is server-side, always.** JWT carries the `role` claim;
  every sensitive route is guarded by a `require_role()` FastAPI dependency,
  not just hidden in the client UI.

---

## 5. Data model

### 5.1 `users`
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| username | str, unique | |
| password_hash | str | bcrypt |
| role | enum(admin, sales) | |
| is_active | bool | |
| created_at | timestamp | |

### 5.2 `products`
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| sku | str, unique | |
| name | str | |
| category | str | e.g. fasteners, hydraulics, filters |
| compatible_models | str/array | which Monitou machine models this fits |
| base_unit | str | always the smallest sellable unit, e.g. "piece" |
| cost_price | decimal | admin-only visibility |
| sale_price | decimal | |
| reorder_threshold | int | in base units |
| is_active | bool | |

### 5.3 `barcodes`
One product can have multiple barcodes for different pack sizes.

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| product_id | FK → products | |
| barcode_value | str, unique | |
| pack_qty | int | how many base units this barcode represents (1 for loose, 50/100 for a box) |
| label | str | e.g. "Single piece", "Box of 100" |

### 5.4 `stock_movements` (the ledger — append-only, never updated)
| column | type | notes |
|---|---|---|
| id | uuid PK, client-generated | idempotency key |
| product_id | FK → products | |
| qty_base_units | int | signed: +300 for purchase, -1 for sale |
| movement_type | enum(sale, purchase, adjustment, stock_take, return, repack) | |
| reference_id | uuid, nullable | links to sale_id / purchase_order_id |
| terminal_id | str | which client device created this |
| created_at_client | timestamp | client's local clock |
| synced_at | timestamp, nullable | set when server accepts it |

Current stock for a product = `SUM(qty_base_units)` for that product. Consider
a materialized `stock_balances` table refreshed on write for fast reads, but
`stock_movements` remains the source of truth.

### 5.5 `sales` / `sale_items`
| sales | |
|---|---|
| id | uuid PK |
| invoice_number | str, unique per series — see numbering below |
| invoice_series | str | one series per terminal, e.g. `T1`, `T2` |
| customer_id | FK, nullable |
| cashier_id | FK → users |
| terminal_id | str |
| total_amount | decimal |
| gst_amount | decimal |
| payment_mode | str |
| created_at_client | timestamp |
| synced_at | timestamp, nullable |

| sale_items | |
|---|---|
| id | uuid PK |
| sale_id | FK → sales |
| product_id | FK → products |
| barcode_id | FK → barcodes, nullable | which barcode was scanned |
| qty_base_units | int | |
| unit_price | decimal | |

**Invoice numbering:** each terminal owns its own series/prefix (`T1-1001`,
`T2-1001`, ...) allocated at setup time — satisfies GST's allowance for
multiple series per location; don't assign one global sequential number
across terminals. **Server-assigned**, not client-generated: `POST /sales`'s
`invoice_number` is optional — when omitted, `services/sales.py` computes the
next sequential number for that `invoice_series` (max existing numeric
suffix + 1, retried on the rare concurrent-collision case). Now that the
client always talks to the server directly, this is simpler and safer than
each terminal maintaining its own counter — the earlier local-counter
approach caused real collisions between a terminal's numbering and unrelated
data (e.g. seed/demo data sharing the same series).

### 5.6 `suppliers` / `purchase_orders` / `purchase_order_items`
Standard supplier + PO structure; goods-received entries generate
`stock_movements` rows with `movement_type = purchase`.

### 5.7 `customers`
Basic B2B/B2C fields; optional credit/outstanding balance tracking if the shop
sells on credit.

### 5.8 Admin dashboard — stats & alerts

The admin panel needs an at-a-glance home screen: sales performance over time,
current stock health, and low-stock warnings. These are **read-only,
derived views** — nothing here is a new source of truth, everything is
computed from `sales`, `sale_items`, and `stock_movements`.

**`GET /reports/sales-summary?period=daily|weekly|monthly&from=&to=`**
- Returns a time-bucketed series: `{ period_start, total_sales, total_gst, invoice_count, top_products[5] }` per bucket.
- `daily` buckets by calendar day, `weekly` by ISO week, `monthly` by calendar month.
- Backed by a query grouping `sales`/`sale_items` by `date_trunc(period, created_at)` — no separate summary table needed at this scale; add a materialized/rollup table later only if query time becomes a problem.

**`GET /reports/stock-stats`**
- Returns: total SKUs, total stock value (`SUM(balance * cost_price)`), count of
  out-of-stock products, count of products below `reorder_threshold`, top 5
  fastest-moving and slowest-moving products (by units sold in last 30 days).
- Cost-price-derived figures are **admin-only** — this endpoint must reject the
  `sales` role entirely, not just hide fields.

**`GET /reports/low-stock-alerts`**
- Returns every product where current balance (from Section 5.4's ledger sum)
  is at or below its `reorder_threshold`, sorted by how far below threshold.
- This is the same query the `jobs/low_stock_alerts.py` scheduled job uses to
  decide what to notify about — keep one shared query function in
  `services/` and call it from both the job and the endpoint, don't duplicate
  the logic.

**Low-stock notification delivery:** on top of the in-app alert list, the
scheduled job should push a notification the admin will actually see without
opening the app — start with a daily digest email (or a simple webhook to
something like Slack/WhatsApp Business API if the shop already uses one);
in-app-only alerts are easy to miss on a small screen. Note the interval as an
open decision in Section 9 (how often — real-time on each sale that crosses
the threshold, or a daily check).

**Client-side:** the dashboard screen calls these three endpoints on load and
on a periodic refresh (e.g. every 5 minutes while the admin panel is open),
and renders them as: a bar/line chart for the sales-summary series, a set of
stat cards for stock-stats, and a plain sortable table for low-stock-alerts
(a table, not a chart — it's a worklist the admin needs to act on).

---

## 6. Environment & tooling setup

### Backend — Docker Compose (recommended: full stack, Postgres)

`docker-compose.yml` at the repo root (`monitou-pos/`) runs the real stack —
Postgres + the FastAPI backend — with one command.

```bash
# from monitou-pos/
docker compose up -d --build      # builds the backend image, starts db + backend
docker compose logs -f backend    # watch it run migrations then boot uvicorn
docker compose exec backend uv run python -m app.seed   # seed test data
docker compose down               # stop (add -v to also wipe the Postgres volume)
```

Backend at `http://localhost:8000`; Postgres exposed on host port **5433**
(not 5432 — avoids clashing with a locally-installed Postgres). The backend
container's entrypoint (`infra/docker/entrypoint.sh`) waits for the DB, runs
`alembic upgrade head`, then starts uvicorn — every `up` is already migrated.

Dockerfile: `infra/docker/Dockerfile.backend` — multi-stage `uv sync --frozen`
build, no unpinned `pip install`. Rebuild after changing `pyproject.toml`/
`uv.lock`: `docker compose build backend`.

### Backend — uv, without the backend containerized (still needs Postgres)

Running the FastAPI process natively (not inside Docker) is fine — but it
still needs a real Postgres to talk to. There's no SQLite fallback; either
run `docker compose up -d db` first (just the database service) and point at
it, or use a Postgres you already have.

```bash
# one-time: install uv (if not already present)
curl -LsSf https://astral.sh/uv/install.sh | sh

# from backend/
uv init --no-readme --package             # if starting fresh
uv add fastapi "uvicorn[standard]" sqlmodel alembic \
       "python-jose[cryptography]" "passlib[bcrypt]" \
       pydantic-settings apscheduler python-escpos weasyprint "psycopg[binary]"
uv add --dev pytest httpx ruff

# app/config.py's default DATABASE_URL already points at the docker-compose
# Postgres on localhost:5433 — override via env var if pointing elsewhere
uv run alembic upgrade head              # apply migrations
uv run uvicorn app.main:app --reload     # run dev server
uv run pytest                             # run tests (isolated in-memory SQLite fixture — see note above)
uv sync                                   # reproduce the exact locked env (CI/deploy)
```

### Client (Node + Tauri)

The client (`client/`) is a **Node/TypeScript project, not uv-managed** — uv
is backend-only. Requires the Rust toolchain (for Tauri's native shell) plus
Node.

```bash
# one-time: Rust toolchain (required by Tauri) + Node (use nvm or similar)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# install Node 20+ via your preferred method

# from client/
npm create tauri-app@latest .            # if starting fresh, pick React + TypeScript template
npm install @fluentui/react-components @tanstack/react-query zustand recharts
npm install @tauri-apps/plugin-http @tauri-apps/plugin-store @tauri-apps/plugin-dialog @tauri-apps/plugin-fs

npm run tauri dev                        # run the dev app (spins up Vite + the Tauri shell)
npm run tauri build                      # produces the Windows installer (MSI/NSIS)
npm test                                  # frontend tests (Vitest)
```

---

## 7. Coding conventions & guardrails

- All API routes are `async def`. DB session is injected via a FastAPI
  dependency (`Depends(get_session)`), never instantiated inside a route.
- Every mutating stock/sale operation goes through
  `services/stock_ledger.py` — never write to `stock_movements` directly from
  a router. This keeps the idempotency and balance-computation logic in one
  place.
- Every route that isn't public (`/auth/login`, `/health`) must depend on
  `get_current_user`. Every admin-only route must additionally depend on
  `require_role("admin")`.
- Money fields are `Decimal`, never `float`.
- All timestamps are stored in UTC; client-local timestamps are kept in a
  separate `created_at_client` column rather than overwriting server time.
- New tables always get an Alembic migration in the same commit — never rely
  on `create_all()` outside of tests.
- Every new endpoint gets at least one pytest test before being considered
  done, including a test for the role-permission boundary (sales user hitting
  an admin route should get 403).
- Every write that carries a client-generated ID (sales, stock movements)
  must stay idempotent by that ID — write a test that submits the same
  request twice and asserts stock/sales are unaffected the second time. This
  is network-retry safety, not offline-sync support (there is no sync layer).

### Frontend (client/)

- All components are functional, written in TypeScript, no `any` unless truly
  unavoidable.
- Build UI from **Fluent UI v9 components first** — reach for a custom
  component only when Fluent UI genuinely has no equivalent; the native-Windows
  look is the whole point of this stack, and hand-rolled components erode it.
- Server data (products, stock, reports) goes through **React Query** —
  no manual `useEffect` + `fetch` + `useState` data-fetching. This gives
  caching, retry, and loading/error states consistently everywhere.
- Local-only UI state (cart contents, current screen, modal open/closed) goes
  in a **Zustand** store, not React Query and not prop-drilled through many
  components.
- Every sale/movement carries a client-generated UUID (`crypto.randomUUID()`)
  — this is the idempotency key the backend relies on; never let the backend
  generate movement/sale IDs.
- Screens call `api/client.ts` directly for every read and write — there is
  no local cache or outbox to write to instead. A failed write (checkout,
  stock adjustment, etc.) must surface a visible, retryable error; never fail
  silently or drop the attempted action.
- Every new screen gets at least a smoke test (renders without throwing,
  role-gated screens don't render admin controls for a `sales` session) before
  being considered done.

---

## 8. Build plan — follow in order

### Phase 0 — Project scaffold
- [x] `uv init` the backend project, set up `pyproject.toml`, folder structure per Section 3
- [x] Basic FastAPI app with a `/health` endpoint
- [x] Alembic initialized, connected to a local SQLite DB for dev
- [x] Confirm `uv run uvicorn app.main:app --reload` works

### Phase 1 — Data model & migrations
- [x] Implement all SQLModel models from Section 5
- [x] Generate and run Alembic migrations for all tables
- [x] Seed script — 18 products across categories, barcodes, suppliers/customers, initial stock, ~55 sample sales over the last 30 days (`app/seed.py`, `uv run python -m app.seed` or `docker compose exec backend uv run python -m app.seed`)

### Phase 2 — Auth & RBAC
- [x] `users` table, password hashing, `/auth/login` issuing JWT with `role` claim
- [x] `get_current_user` and `require_role()` dependencies
- [x] Tests confirming sales role is blocked from admin routes

### Phase 3 — Product & barcode catalog (admin)
- [x] CRUD endpoints for products (admin-only for write, both roles for read minus cost price)
- [x] CRUD endpoints for barcodes, enforcing one `pack_qty` per barcode
- [x] Tests: scanning a box barcode resolves to the right base-unit multiplier

### Phase 4 — Stock ledger
- [x] `services/stock_ledger.py`: append movement, compute balance, idempotent write by ID
- [x] Endpoint for admin stock adjustments and purchase receiving
- [x] Tests: concurrent/duplicate movement IDs don't double-count; negative-balance detection flag works

### Phase 5 — Sales / POS flow
- [x] `/sales` endpoint: accepts a sale with line items, writes matching `stock_movements` (sale type) atomically with the sale record
- [x] Per-terminal invoice series/numbering
- [x] GST invoice PDF generation
- [x] Tests: a sale correctly decrements stock by the scanned barcode's `pack_qty`

### Phase 6 — Offline sync endpoints — **built, then removed**
`/sync/push` and `/sync/pull` (with a matching local SQLite cache/outbox on
the client) were built and working, but caused repeated, hard-to-debug
data-integrity issues (stale caches, invoice-number collisions between
independent local counters, upsert conflicts on a data reset) that kept
surfacing as "checkout succeeded but doesn't show up" reports. Removed in
favor of the client always talking to the server directly — see Section 1
and Section 4. `app/routers/sync.py`, `app/services/sync_service.py`,
`app/schemas/sync.py`, and the client's `db/localDb.ts` / `sync/syncWorker.ts`
no longer exist. What replaced the client-side pieces: `GET /barcodes/search`
(catalog search — see Phase 8) and server-assigned invoice numbers
(Section 5.5) — both now live entirely on the server, called directly.

### Phase 7 — Reporting & admin dashboard
- [x] `GET /reports/sales-summary` with `daily|weekly|monthly` bucketing (Section 5.8)
- [x] `GET /reports/stock-stats`: total stock value, out-of-stock count, below-threshold count, top 5 fast/slow movers — admin-only, verify sales role gets 403
- [x] Shared `services/` query function for "products at or below reorder_threshold", used by both `GET /reports/low-stock-alerts` and the scheduled job below
- [x] APScheduler job (`jobs/low_stock_alerts.py`) running the shared low-stock query on a schedule — delivery channel logs the digest for now; email/webhook wiring is still an open decision, see Section 9
- [x] Tests: sales-summary bucket totals match a hand-computed fixture; stock-stats cost-derived fields are rejected for the sales role; low-stock query returns the same result via both the endpoint and the job's internal call

### Phase 8 — Windows client (Tauri + React + Fluent UI)
- [x] Scaffold with `npm create tauri-app@latest` (React + TypeScript template), confirm `npm run tauri dev` opens a window — built and ran on macOS as `target/debug/monitou-pos-client` without crashing; not verified on Windows
- [x] Wire up Fluent UI v9's `FluentProvider` + theme at the app root
- [x] `Login.tsx`, calling `/auth/login` via `api/client.ts`, storing the JWT with `plugin-store` (`session.ts`, rehydrated on startup) — the only thing persisted locally; not a data cache
- [x] `PosBilling.tsx`: search-as-you-type over barcode/SKU/name (debounced, calls `GET /barcodes/search` directly — no local catalog), cart via the Zustand store, checkout calls `POST /sales` synchronously and waits for the result. Qty is editable per line — a box scan defaults to its `pack_qty` (e.g. 100) but the cashier can edit it down for a partial sale from an opened box; the backend trusts the edited `qty_base_units` directly rather than re-deriving it from the barcode. A failed checkout shows an error and leaves the cart intact for retry — no local queue to fall back on.
- [x] `ProductAdmin.tsx` / `StockAdmin.tsx`: admin-only screens (hidden for `sales` sessions client-side, still enforced server-side)
- [x] `Dashboard.tsx`: sales-summary chart (Recharts, daily/weekly/monthly toggle), stock-stats cards, low-stock-alerts table — calls the three Section 5.8 endpoints via React Query, refreshes periodically while open
- [x] Receipt printing: Rust command wrapping the `escpos` crate (`src-tauri/src/printer.rs`), invoked from the frontend via Tauri's `invoke()`. **Decision made:** `NetworkDriver` (TCP, e.g. port 9100) only — dropped the `usb`/`native_usb` features to avoid libusb linking on the Windows build machine; USB-connected printers aren't supported yet. A per-shop PDF-invoice-via-print-dialog option remains available for printers that don't fit network printing.
- [ ] `npm run tauri build` — confirm the MSI/NSIS installer runs cleanly on a clean Windows machine — not run; needs an actual Windows build machine, not this macOS dev box

**Dev-machine note:** built and tested on macOS (no Windows box available). Needs the Rust
toolchain (`rustup`) in addition to Node — installed via `curl .../rustup.rs | sh` per Section 6.
`cargo check` and `npm run tauri dev` both succeed and the compiled binary runs without
crashing; the on-screen UI was never visually confirmed on Windows (Chrome-based visual QA
was done for the login/theme design and the search dropdown — see git history — but that's
not a substitute for a real Windows run). Automated coverage: `npm test` (Vitest) covers
`cart.ts` (line/qty logic). Component-level render tests for the Fluent-UI screens were
attempted and dropped: `tabster` (a Fluent UI focus-management dependency) ships a
package.json with `"type": "module"` but `"main"` pointing at a `.cjs` build with no
`"exports"` map, which breaks under Vitest's Node-style SSR module linking regardless of
`resolve.alias`, `server.deps.inline`, or `deps.optimizer.web.include` — not fixable from this
repo's config. Doesn't affect the real app (a real browser/WebView resolves it fine); only
blocks jsdom-based render tests.
Before shipping: actually launch the app on Windows against a running backend and a real
network thermal printer, and walk the golden path (login → search/scan → checkout →
dashboard → print). Since there's no offline fallback, also confirm the shop's actual network
path to the backend is reliable before relying on this in a live till.

### Phase 9 — AWS deployment
- [x] Dockerfile for backend using `uv sync --frozen` (`infra/docker/Dockerfile.backend`) — built, run, and migration-tested locally against Postgres via `docker compose`; not yet pushed anywhere
- [ ] Push image to ECR
- [ ] RDS PostgreSQL (Multi-AZ) provisioned, credentials in Secrets Manager
- [ ] ECS Fargate service + ALB + target group, HTTPS via ACM
- [ ] Run Alembic migrations against RDS as part of deploy
- [ ] CloudWatch alarms for 5xx rate and CPU/memory
- [ ] Point client config at the production API URL

### Phase 10 — Hardening & polish
- [ ] Load-test `/sales` and `/barcodes/search` under realistic POS concurrency (several terminals checking out at once)
- [ ] Verify GST invoice numbering has no gaps under concurrent checkouts across terminals sharing a series
- [ ] Backup strategy: RDS automated snapshots + periodic export to S3
- [ ] Document admin runbook: how to resolve a negative-stock flag, how to add a new terminal/invoice series
- [ ] Since there's no offline fallback, document what a cashier should do during a network/backend outage (this is now a real operational gap, not just a degraded mode)

---

## 9. Open decisions to confirm before/while building

- ~~Offline-first vs. always-online~~ — **resolved: always-online.** The
  client has no local database; every action requires a live connection to
  the backend. See Section 1/4. Revisit only if a shop's network reliability
  turns out to be a real operational problem in practice.
- Single shop only for now, or should terminal/branch support be built in from
  the start? (Affects `terminal_id` scoping and invoice series allocation —
  more relevant now than under the old design, since invoice numbers are
  server-assigned per series rather than each terminal counting locally.)
- ~~Should `repack` movements (opening a box to sell loose) be tracked
  explicitly, or is a simple total piece count sufficient?~~ — **partially
  resolved:** a simple piece count is sufficient for *selling* from an opened
  box — `POST /sales`'s `qty_base_units` is client-authoritative (the cashier
  can edit a box scan's default `pack_qty` down for a partial sale), no
  separate `repack` movement gets written. Still open: nothing yet records
  the *other* direction — that a box was opened at all, if you want to track
  "opened but not fully sold" boxes as distinct from sealed ones.
- Retention/backup policy for `stock_movements` — this table grows forever;
  decide on archiving strategy early if volume will be high.
- Exact GST rate handling — flat rate per shop or per-product HSN-based rates?
- Low-stock notification channel and frequency — daily digest vs. real-time on
  each sale that crosses the threshold, and email vs. a chat webhook (Slack/
  WhatsApp Business API) if the shop already uses one.
- ~~ESC/POS thermal printer integration from Rust~~ — **resolved in Phase 8:**
  the `escpos` crate's `NetworkDriver` (plain TCP, e.g. port 9100) works
  without any native library linking. Still open: USB-connected printers
  aren't supported (only network) — add `UsbDriver`/`native_usb` back if a
  shop needs it, at the cost of libusb on the Windows build machine.

---

## 10. Definition of done for each phase

A phase is not complete until: migrations run cleanly from scratch, all new
endpoints have passing tests including a role-permission test, and the
relevant section of this file is updated if the implementation diverged from
the plan above.

---

## 11. Multi-tenant SaaS: Plan, Feature Entitlement & Usage Limit system

This section is the architecture and migration plan for turning this
single-shop app into one multi-tenant application serving BASIC / ESSENTIAL /
ENTERPRISE customers from the same codebase. **One application, one
codebase, data-driven plan config** — never `if plan == "X"` scattered
through routers/components. Follow the stage order below the same way
Section 8 is followed: don't start a stage until the previous one is
migrated and tested.

### 11.1 Reality check against the current codebase (read before assuming a module exists)

This app today is a **single shop, single location, two-role** POS + basic
inventory system. It is not yet the ERP the full feature catalog (11.5)
describes. Concretely:

- **No tenant concept anywhere.** `users`, `products`, `sales`, etc. are one
  global set of rows. This is the biggest structural gap — see 11.2.
- **No warehouses/branches at all.** There's one implicit location. The
  `WAREHOUSE_MANAGEMENT` / `STORAGE_LOCATION` / `INTER_WAREHOUSE_TRANSFER` /
  branch-limit features have **no backing module yet** — they need to be
  built, not just gated.
- **Purchasing is minimal.** `suppliers` + `purchase_orders` exist
  (draft/ordered/partially_received/received/cancelled status enum) but
  there is no Purchase Request, no PO approval workflow, no GRN entity, no
  vendor returns. `GRN`/`PARTIAL_GRN`/`PURCHASE_REQUEST*` features have no
  backing module yet.
- **Sales is POS-only.** `sales`/`sale_items` cover a walk-in-style
  checkout. No quotations, no reservations, no pick lists, no dispatch/
  transport tracking, no customer returns. Most of the `sales` module's
  feature catalog has no backing module yet.
- **No barcode *generation/printing/scanning workflow*.** `barcodes` today
  is just "a barcode value maps to a product + pack_qty," looked up by
  `GET /barcodes/search`. There's no label generation, no dedicated
  scan-driven GRN/picking flow, no wrong-part validation.
- **No cycle counting, quarantine stock, ageing/dead-stock analytics.**
  `PHYSICAL_STOCK_VERIFICATION`/`STOCK_VARIANCE`/`DAMAGED_STOCK` have a thin
  analogue (stock adjustments + the negative-balance flag) but no dedicated
  variance/approval workflow.
- **RBAC is binary** (`admin`/`sales` enum), not `CUSTOM_ROLES`/
  `GRANULAR_PERMISSIONS`. There's no permission table.
- **What already exists and maps cleanly:** `PRODUCT_MASTER`, `HSN_GST`
  (schema supports it, not surfaced), `MINIMUM_STOCK`/`REORDER_LEVEL`/
  `LOW_STOCK_ALERT`/`OUT_OF_STOCK_ALERT`, `STOCK_LEDGER`, `STOCK_ADJUSTMENT`,
  `VENDOR_MASTER`/`VENDOR_PURCHASE_HISTORY`, `PURCHASE_ORDER` (basic, no
  approval), `CUSTOMER_MASTER`, `BASIC_SALES_ORDER` (as POS checkout),
  `STOCK_AVAILABILITY`, `BASIC_DASHBOARD`/`BASIC_REPORTS`.

**Implication:** Stages 1–6 (schema, tenancy, entitlement service, limit
service, backend guards, frontend gate) are buildable now and are
plan-catalog-agnostic infrastructure — they don't need the missing modules
to exist. Stages that gate a *specific* feature (e.g.
`require_feature("INTER_WAREHOUSE_TRANSFER")`) can only be wired onto a
router once that router exists. Where a catalog feature has no backing
module yet, the feature row is still seeded (so the Plan page and upgrade
comparison screen are accurate/sellable today) but nothing in the app calls
`require_feature()` for it until that module is built as separate,
explicitly-scoped work.

### 11.2 Tenant isolation strategy

- Add `tenant_id: uuid.UUID` (FK → `tenants.id`, indexed, **not nullable**
  after backfill) to every existing business table: `users`, `products`,
  `barcodes`, `stock_movements`, `suppliers`, `purchase_orders`,
  `purchase_order_items`, `sales`, `sale_items`, `customers`. Backfill
  strategy for the existing single dataset: create one `Tenant` row (e.g.
  `tenant_code="MONITOU-001"`) and set it as every existing row's
  `tenant_id` in the same migration, then add the `NOT NULL` constraint.
- JWT gains a `tenant_id` claim, set at login from the authenticating user's
  `tenant_id`. `get_current_user` already decodes the token — extend it to
  also resolve and attach the tenant (and reject if the tenant is
  suspended, deferring to 11.8's grace-period policy).
- **Central scoping, not per-router filtering.** Add a `get_current_tenant`
  dependency and a small query helper — e.g. `tenant_scoped(session,
  tenant_id, Model)` returning a `select(Model).where(Model.tenant_id ==
  tenant_id)` — and require every router to build queries through it.
  A code-review checklist item (11.10) covers catching a missed filter.
- **Defense in depth: Postgres Row-Level Security.** Because "every backend
  query must automatically scope to the tenant, even against a
  manually-modified request" is a hard requirement, don't rely solely on
  every developer remembering the `.where()` clause. Enable RLS on every
  tenant-scoped table with a policy keyed on `current_setting('app.tenant_id')`,
  and have `get_session` (or a wrapping dependency) execute `SET
  app.tenant_id = '<uuid>'` at the start of each request's transaction. A
  forgotten application-level filter then still can't leak cross-tenant
  rows — the database itself refuses. This is the single most important
  mitigation for 11.9's top risk.
- Cross-tenant test (see 11.11): authenticate as a Tenant A user, request a
  Tenant B record's ID directly (path param or body), assert 404 (not 403 —
  don't reveal the record exists).

### 11.3 Backend entitlement service

`app/services/entitlements.py`:

```python
def can_use_feature(session, tenant_id: uuid.UUID, feature_code: str) -> bool:
    # 1. TenantFeatureOverride for (tenant_id, feature_code) — if a row
    #    exists, its `enabled` wins outright (grants or revokes).
    # 2. Else PlanFeature for the tenant's active_plan_id — `enabled` there.
    # 3. Else False (unknown feature code fails closed).

def require_feature(feature_code: str):
    # FastAPI dependency factory. Depends(get_current_tenant) internally.
    # 403 with the structured FEATURE_NOT_AVAILABLE body (11.6) if
    # can_use_feature() is False.
```

`required_plan` in the 403 body is computed by finding the cheapest plan
(by `setup_price`) whose `PlanFeature` enables that code — data-driven, not
a hard-coded lookup table.

### 11.4 Backend usage limit service

`app/services/usage_limits.py`:

```python
def check_limit(session, tenant_id, limit_code: str, increment: int = 1) -> None:
    # resolve limit = TenantLimitOverride else PlanLimit for active plan
    # read UsageCounter.current_value for (tenant_id, limit_code)
    # if current_value + increment > limit: raise PlanLimitReached(...)
    #   -> structured 409 PLAN_LIMIT_REACHED (11.6)

def increment_usage(session, tenant_id, limit_code: str, by: int = 1) -> None: ...
def decrement_usage(session, tenant_id, limit_code: str, by: int = 1) -> None: ...
```

Call `check_limit` **before** the create commits, and `increment_usage` /
`decrement_usage` in the same service function that creates/deactivates the
counted entity (user activation/deactivation, warehouse creation, product
creation) — one write path per metric, never a scattered `COUNT(*)`.
Metric codes for this build: `MAX_USERS`, `MAX_BRANCHES`, `MAX_WAREHOUSES`,
`MAX_SKUS`.

### 11.5 Feature catalog, plan mapping, limits

Centralized in `backend/app/plan_catalog.py` (already implemented — 11.12)
and nowhere else. 80 feature codes across 9 modules
(`inventory_catalog`, `warehouse`, `purchase`, `sales`, `barcode`,
`stock_analytics`, `dashboard`, `reports`, `admin`); BASIC = 28 features,
ESSENTIAL = BASIC + 34, ENTERPRISE = all 80. Limits: `MAX_USERS`/
`MAX_BRANCHES`/`MAX_WAREHOUSES`/`MAX_SKUS` per the table in the original
spec (5/1/1/5000, 15/2/2/15000, 30/5/5/50000). Backup retention
(7/15/30 days) is informational metadata for the Plan page, enforced by the
backup job/infra rather than `check_limit`.

Note: "Basic RBAC" and "Basic Audit Log" (mentioned in the spec's BASIC
feature list) have no dedicated feature codes — the base two-role split and
a plain audit trail are core, ungated behavior; `CUSTOM_ROLES`/
`GRANULAR_PERMISSIONS`/`FULL_AUDIT_LOG`/`ADVANCED_AUDIT_LOG` are the gated
upgrades on top of that baseline.

### 11.6 Backend feature guard — structured error contract

```python
@router.post("/warehouse-transfers")
async def create_transfer(
    ...,
    _: None = Depends(require_feature("INTER_WAREHOUSE_TRANSFER")),
    _perm: User = Depends(require_permission("CREATE_TRANSFER")),  # RBAC, separate layer — 11.9
):
```

403 body on a feature gate failure:
```json
{
  "code": "FEATURE_NOT_AVAILABLE",
  "feature": "BARCODE_GENERATION",
  "required_plan": "ESSENTIAL",
  "message": "Barcode Generation is available in Essential and Enterprise plans."
}
```

409 body on a limit gate failure:
```json
{
  "code": "PLAN_LIMIT_REACHED",
  "limit": "MAX_USERS",
  "limit_value": 5,
  "current_value": 5,
  "message": "Your Basic plan supports up to 5 active users. Upgrade your plan or purchase additional user capacity."
}
```

Both are raised as `HTTPException`-derived exceptions with a shared FastAPI
exception handler so every router gets the same JSON shape without
duplicating it.

### 11.7 Frontend FeatureGate architecture

- `GET /tenant/me/entitlements` (new endpoint) returns, for the
  authenticated user's tenant: `{ plan_code, subscription_status,
  features: { <code>: bool }, limits: { <code>: { used, max } } }`.
  Fetched once via React Query on login, cached, invalidated on
  plan/override changes (platform admin action or explicit refresh).
- `useFeature(code: string): boolean` — reads that cached snapshot; no
  component computes plan logic itself.
- `<FeatureGate feature="BARCODE_GENERATION" mode="hide" | "lock" |
  "disable">` — `hide` renders nothing (sidebar items), `lock` renders the
  locked-feature card (icon, required plan, one-line explanation, Upgrade
  CTA), `disable` clones its child as a disabled control with a tooltip
  ("Inter-Warehouse Transfer requires Enterprise."). Default `mode="lock"`.
- Never trusted for security — every gated action still hits a
  `require_feature`-guarded endpoint; the frontend gate is UX only.

### 11.8 Subscription status & grace period

`SubscriptionStatus`: `ACTIVE | EXPIRING | EXPIRED | SUSPENDED |
GRACE_PERIOD`. A scheduled job (alongside the existing
`jobs/low_stock_alerts.py` pattern) transitions `ACTIVE → EXPIRING` inside a
configurable window before `renewal_date`, and `EXPIRING → EXPIRED` after
it; `EXPIRED → GRACE_PERIOD` is automatic with a configurable grace-period
length (platform-admin-configurable, not hard-coded), and only
`GRACE_PERIOD → SUSPENDED` needs an explicit platform-admin action or a
final automatic cutoff — access is never destroyed the instant a date
passes. `get_current_tenant` reads this status and attaches it to the
request context so the frontend can show a persistent banner during
`EXPIRING`/`GRACE_PERIOD`/`EXPIRED` without blocking every route itself
(only `SUSPENDED` blocks non-billing routes).

### 11.9 Multi-tenant security risks identified

1. **Missed `tenant_id` filter in a hand-written query** — the single
   biggest risk of converting an existing single-tenant codebase; mitigated
   by RLS (11.2), not just code review.
2. **IDOR via path/body IDs** — e.g. `GET /products/{id}` today does
   `session.get(Product, product_id)` with no ownership check at all. Every
   such lookup must add `.where(tenant_id == ...)` or rely on RLS to make
   the row invisible regardless.
3. **JWT tenant_id spoofing** — the claim must be server-derived at login
   and signed, never accepted from a request body/header.
4. **Cross-tenant enumeration via unique constraints** — `products.sku`,
   `users.username`, `barcodes.barcode_value` are currently globally unique;
   they must become unique **per tenant** (`UNIQUE(tenant_id, sku)`, etc.),
   or Tenant A can learn whether Tenant B has a given SKU/username from a
   409 conflict response.
5. **Background jobs** (`low_stock_alerts.py`) currently query with no
   tenant scoping at all — must be rewritten to iterate tenants and scope
   each pass, not to become one cross-tenant pass with tenant info attached
   after the fact.
6. **Platform Admin privilege boundary** — Platform Admin auth must be a
   fully separate credential/role space from tenant users (11.13), never
   "an admin user with an extra flag" in the same `users` table, so a
   tenant-side privilege escalation bug can't reach platform-admin actions.

### 11.9a Operational note: RLS needs a non-superuser DB app role

Postgres superusers bypass Row-Level Security **unconditionally**, `FORCE
ROW LEVEL SECURITY` included — this is not configurable. The local
`docker-compose` Postgres's default user is a superuser, so RLS is silently
inert against it; it was verified instead by creating a temporary
`NOSUPERUSER` role locally and confirming empty-`app.tenant_id` reads
return 0 rows and a mismatched-tenant `INSERT` is rejected (11.12's Stage 2
row). **Before relying on RLS in any real environment (including staging),
confirm the app's DB user is not a superuser/RDS-master role** — AWS RDS's
default master user is `rds_superuser`, a restricted role that (unlike a
true Postgres superuser) does **not** bypass RLS, but a hand-rolled EC2/
self-managed Postgres's default user typically is a true superuser and
would need a dedicated, non-superuser application role.

### 11.9b Login now requires a tenant code

`username` is unique per tenant, not globally (11.9.4), so `POST
/auth/login` alone can't disambiguate which tenant's `admin1` is signing
in. Rather than inventing a non-standard field, the tenant code rides in
the OAuth2 password-grant form's existing optional `client_id` field (e.g.
`client_id=MONITOU-001`) — this keeps `/auth/login` working with
`OAuth2PasswordBearer`'s standard flow and Swagger's built-in Authorize
dialog, which already has a `client_id` input. The Windows client's login
screen (Stage 6+) needs a tenant-code field added alongside username/
password; it isn't there yet since Phase 8 predates tenancy.

### 11.10 Code-review checklist addition (Section 7 extension)

Once tenancy lands, add to Section 7's guardrails: every new query against
a tenant-scoped table must go through the `tenant_scoped()` helper or rely
on RLS being enabled for that table (verified once per table, not
per-query); every new unique constraint on a tenant-scoped table must
include `tenant_id`; every new endpoint accepting an entity ID must be
covered by a cross-tenant-403/404 test (11.11).

### 11.11 Test plan (Stage 14, tracked here so it isn't lost)

Basic user blocked from Essential-only endpoint; Essential user blocked from
Enterprise-only endpoint; Enterprise user passes all feature gates; 6th user
create on Basic returns `PLAN_LIMIT_REACHED`; 2nd warehouse blocked on
Basic, allowed on Essential, 3rd blocked on Essential; feature override
unlocks a restricted feature for one tenant without touching its plan;
limit override raises capacity for one tenant; `FeatureGate` renders
hide/lock/disable correctly per mode and per entitlement snapshot; manually
calling a restricted API with a crafted request still 403s; Tenant A
request for a Tenant B record ID 404s; plan upgrade leaves all existing
tenant data byte-for-byte unchanged; plan downgrade below current usage
preserves existing rows and blocks only new creation; expired-tenant
behavior matches the configured grace-period policy at each status.

### 11.12 Staged build status

| Stage | Scope | Status |
|---|---|---|
| 1 | Plan/Feature/PlanFeature/PlanLimit/Tenant/Subscription/TenantFeatureOverride/TenantLimitOverride/UsageCounter schema + migration; `plan_catalog.py` + `seed_plans.py` seeding 3 plans, 80 features, plan_features, plan_limits | **Done** — migration `27ff755cb588`, verified idempotent, `28/62/80` features per plan confirmed against spec |
| 2 | `tenant_id` on every business table + backfill + RLS + `get_current_tenant` + JWT claim + per-tenant unique constraints (11.9.4) | **Done** — migrations `4c4b99b6eb8b` (backfill, per-tenant `UNIQUE(tenant_id, ...)` on `users.username`/`products.sku`/`barcodes.barcode_value`/`sales.invoice_number`) + `9196eb11b8d2` (RLS); `app/tenancy.py` (`tenant_scoped`, `get_tenant_owned`, `set_rls_tenant`); every router/service now scopes by `tenant_id`; `low_stock_alerts.py` job loops per-tenant. Cross-tenant isolation tests in `tests/test_tenancy.py`. RLS **verified against real Postgres with a non-superuser role**: 0 rows visible with `app.tenant_id` unset, correct rows for the right tenant, `INSERT` of a row claiming a different tenant is rejected — see 11.9a. |
| 3 | `services/entitlements.py` (`can_use_feature`, `require_feature`) | **Done** — resolution order override-then-plan-then-deny; `require_feature()` FastAPI dependency raises the exact `FEATURE_NOT_AVAILABLE` structured 403 from 11.6, with `required_plan` and the plan-list message computed live from `PlanFeature` (never hard-coded). 12 tests in `tests/test_entitlements.py`, built against the real seeded catalog rather than fixture rows. Not yet wired to any router — that's Stage 5. |
| 4 | `services/usage_limits.py` (`check_limit`, `increment_usage`/`decrement_usage`) wired into user creation (first consumer, since `users` already exists) | **Done, plus one more consumer** — wired into both `POST /users` (MAX_USERS; this endpoint didn't exist before, added since Stage 4 needed a create-user flow to enforce against) and `POST /products` (MAX_SKUS, since that create-flow already existed). Branches/warehouses have no backing module yet (11.1) so their counters exist but nothing increments them. One-time `app/reconcile_usage_counters.py` backfills `usage_counters` for tenants whose users/products predate this stage — run and verified against the local dev tenant (2 users, 18 products, matches exactly). 7 tests in `tests/test_usage_limits.py`, including the exact `PLAN_LIMIT_REACHED` message from the spec and override-raises-capacity. |
| 5 | Apply `require_feature`/`check_limit` guards to existing routers (products, users, purchase_orders, sales) — the only routers that exist today | **Done** — every existing router now depends on `require_feature`: `products.py` → `PRODUCT_MASTER`, `stock.py` → `STOCK_ADJUSTMENT`/`GRN`/`STOCK_LEDGER`, `sales.py` → `BASIC_SALES_ORDER`, `reports.py` → `BASIC_REPORTS`/`LOW_STOCK_ALERT` plus a **per-field** gate on `stock-stats` (`fastest_moving`/`slowest_moving` nulled out without `FAST_MOVING_ANALYSIS`/`SLOW_MOVING_ANALYSIS` — same pattern as `ProductRead` vs `ProductReadPublic`, plan-driven instead of role-driven). `users.py` deliberately left ungated (11.5: base user management isn't a catalog feature). `barcodes.py` splits the judgment call explicitly in code comments: `POST /barcodes` (admin catalog management) → `BARCODE_GENERATION` (Essential+); `GET /barcodes/search` and `GET /barcodes/{value}` (checkout-time lookup) stay under `BASIC_SALES_ORDER` since gating them behind `BARCODE_SCAN` would break Basic-tier POS checkout, which this app's entire billing flow depends on — see the reasoning at the top of Stage 5's router diff. 5 new tests in `tests/test_feature_guards.py` (Basic blocked from creating a barcode with the exact spec message, Essential/Enterprise allowed, stock-stats analytics fields suppressed/shown correctly). Full suite: 66 passed, 1 pre-existing unrelated failure. **Follow-up:** the backend suppression existed from day one, but `screens/Dashboard.tsx` never actually rendered `fastest_moving`/`slowest_moving` at all — a Basic tenant and an Essential tenant looked identical because the section simply didn't exist on screen. Added it wrapped in `<FeatureGate feature="FAST_MOVING_ANALYSIS">`/`SLOW_MOVING_ANALYSIS`, so Basic now sees an explicit locked upsell card instead of nothing, and Essential/Enterprise see the real table — the plan difference is visible without opening Settings. |
| 6 | `useFeature`, `<FeatureGate>`, `GET /tenant/me/entitlements` | **Done** — `GET /tenant/me/entitlements` (`app/routers/tenant.py`) returns `{ plan_code, plan_name, tenant_status, features: {code: bool}, feature_info: {code: {name, required_plan, message}}, limits: {code: {used, max}} }` for the full 80-code catalog and all four limit codes; `feature_info`/`feature_not_available_error` now share one `describe_feature()` so the frontend's locked-feature text and the backend's 403 message can never drift apart. Frontend: `hooks/useEntitlements.ts` (`useEntitlements`/`useFeature`/`useFeatureInfo`/`useLimit`, React Query-cached; **revised post-ship** — originally a 5min staleTime on the "entitlements change on a rare event" assumption, but that meant a Platform Admin's plan/override change didn't reach an already-open tenant session for up to 5 minutes, with no websocket to push it sooner. Now a 15s `staleTime` + `refetchInterval` + `refetchOnWindowFocus`, same tradeoff `Dashboard.tsx` already makes with its own polling — cheap at this app's scale) and `components/FeatureGate.tsx` (`hide`/`lock`/`disable` modes; `lock` renders a card with `LockIcon` + the plan-static message + an inert "View plans" CTA, wired to a real target once Stage 9/10 exist). 3 backend tests + 4 frontend logic tests (`resolveFeature`, fails closed on missing/loading data) — `tsc --noEmit` and `npm test` both clean. **Not yet wired into any screen** — nothing renders `<FeatureGate>` yet, that's Stage 8's job (sidebar) and beyond; consistent with Phase 8's noted jsdom/tabster limitation, this couldn't be render-tested either, only logic-tested + typechecked. |
| 7 | *(folded into Stage 1 — done alongside schema since seeding is needed to verify the schema at all)* | Done |
| 8 | Plan-aware sidebar in the client | **Done, as a top tab bar** — this app has a top `TabList` (Section 8's original UI), not a sidebar; per the spec's own "maintain consistent UX, avoid completely different app layouts" instruction, Stage 8 made *that* plan-aware rather than introducing a new sidebar layout the rest of the app doesn't have. `App.tsx` now drives both the tab list and the content panel off one `NAV_ITEMS` config (`{key, label, requiredFeature, adminOnly, render}`), each item wrapped in `<FeatureGate mode="hide">` for the plan layer plus an explicit `role === "admin"` check for the RBAC layer — the two-layer principle from CLAUDE.md's "IMPORTANT DESIGN PRINCIPLE" made literal in the nav code, not just in routers. Added **BarcodeAdmin.tsx** (new screen + `api.createBarcode()`) as the first real differentiated nav item — `POST /barcodes` had a backend endpoint since Stage 5 but no UI at all; gated by `BARCODE_GENERATION`, it's the one tab that actually appears/disappears by plan today (every other existing screen maps to an always-on Basic-tier feature, so this was necessary to have anything to demonstrate). `tsc --noEmit` clean, 13/13 client tests pass. **Verification limitation surfaced and documented, not hidden:** both `@tauri-apps/plugin-http` (used for every API call) and `@tauri-apps/plugin-store` (session persistence) require the real Tauri IPC bridge and throw `Cannot read properties of undefined (reading 'invoke')` outside an actual Tauri window — confirmed by hand against a plain browser tab, consistent with Phase 8's existing note that this app was never browser-tested, only run as the real Tauri binary. This blocks claude-in-chrome-based visual verification entirely (not just component-render-testing, which was already known-blocked); full UI verification of Stage 8 needs `npm run tauri dev` on a machine with the Rust toolchain, not done here. Along the way, fixed two related pre-existing robustness gaps unrelated to plan-gating itself but that this exercise surfaced: `AppContext.tsx`'s `restoreSession()` and `Login.tsx`'s `saveSession()` calls had no `.catch()`, so a `plugin-store` failure (missing Tauri context, or in production a corrupted store file) left the app on a permanent blank screen or silently dropped a successful login — both now fail soft instead of fail blank. Two demo tenants (`DEMO-BASIC`, `DEMO-ESSENTIAL`, user `admin`/`demo1234`) were seeded into the local dev Postgres for this and left in place for future manual testing. |
| 9 | Plan & Subscription settings page | **Done** — new `Subscription`-lookup service (`app/services/subscriptions.py`: `get_current_subscription`, `ensure_subscription`) since no tenant had a subscription row before this stage; `GET /tenant/me/entitlements` extended with a `subscription: {status, start_date, end_date, renewal_date, setup_fee, annual_amc} \| None` field and `feature_info[code].module` (needed to group "enabled capabilities" by module on the page). Frontend: `screens/PlanSubscription.tsx` under the new admin-only "Settings" tab — current plan/setup package, account status, subscription status + AMC dates, a usage bar per limit code (colors shift brand→warning→error near/at the cap), and enabled capabilities grouped by module as badges. "View Plans"/"Request Upgrade" are present but stubbed (show an inline notice) — Stage 10 doesn't exist yet to navigate to, and per the spec neither button may change the plan directly regardless. "Settings" is the first nav item with no `requiredFeature` — it has to stay reachable on every plan, including the one it's telling you to upgrade off of. 4 backend tests (including the exact subscription fields against Basic's real pricing), `tsc --noEmit` clean, 13/13 client tests. Backfilled subscription rows for the 3 existing dev-Postgres tenants (`MONITOU-001`, `DEMO-BASIC`, `DEMO-ESSENTIAL`). Live browser verification still blocked by the Tauri-IPC limitation noted in Stage 8 — not re-attempted, same root cause. |
| 10 | Upgrade comparison screen | **Done** — new `upgrade_requests` table (migration `f7481532a996`; not RLS-protected, same deferral reasoning as `tenant_feature_overrides`/`tenant_limit_overrides`/`subscriptions` in 11.9a: Platform Admin needs cross-tenant access and that bypass role doesn't exist until Stage 11) plus `services/plan_comparison.py::build_plan_comparison` — deliberately reads `PlanFeature` defaults, not `can_use_feature()`, since a comparison chart answers "what does each plan normally include," not "what does this one tenant have after its overrides." Three new endpoints: `GET /tenant/me/plan-comparison`, `POST`/`GET /tenant/me/upgrade-requests` (admin-only; creates a `pending` row and **never** touches `Tenant.active_plan_id` — approving/rejecting is Platform Admin's job, Stage 11+). Frontend: `screens/PlanComparison.tsx` — 3-column table (Basic/Essential/Enterprise), current plan badged, Essential badged "Recommended", every catalog feature as a ✓/— row grouped by module, and a "Request upgrade" button per non-current plan (swaps to "Upgrade requested" once a pending request exists) opening a confirmation dialog with an optional note. `PlanSubscription.tsx`'s "View Plans"/"Request Upgrade" buttons now actually navigate here (replacing Stage 9's stub) via a plain `useState` toggle — no router added, consistent with this app's existing tab-switching pattern. 6 new backend tests (current/recommended flags, exact plan pricing, upgrade request creates without changing the tenant's plan, rejects same-plan/unknown-plan/non-admin, list scoped per tenant) — 76/77 backend total (1 pre-existing unrelated). `tsc --noEmit` clean, 13/13 client tests. Live browser verification still blocked by the Stage 8 Tauri-IPC limitation. |
| 11 | Platform Super Admin area (separate auth space per 11.9.6) | **Done, backend and frontend** — `platform_admins` (separate table, no `tenant_id`, no relation to `users`) and `platform_audit_log` (append-only). New JWT audience claim (`aud: "tenant-user"` vs `"platform-admin"`) is the actual separation mechanism — `get_current_user` and the new `get_current_platform_admin` (`auth/platform_deps.py`) each reject the other's token outright, verified by test in both directions. **Correction while building this:** `TenantFeatureOverride.approved_by`/`TenantLimitOverride.approved_by`/`UpgradeRequest.decided_by` were wrongly FK'd to `users.id` back in Stages 1/10 — overrides and upgrade-request decisions are exclusively Platform Admin actions, so they're re-pointed at `platform_admins.id` (no real data existed in those columns yet, so a straight migration fix, not a backfill). Endpoints: dashboard stats, tenant list, tenant detail (including the tenant's `users` — the one place this stage reads an RLS-protected table cross-tenant, worked around by calling `set_rls_tenant` for that one tenant first; see the long comment atop `routers/platform_admin.py` for why a real `BYPASSRLS` platform-admin DB role is still an open production-infra item), change-plan (also auto-approves a matching pending `UpgradeRequest`, closing the Stage 10 loop), feature-override, limit-override, suspend/reactivate (suspend immediately blocks that tenant's `/auth/login`, verified), extend-subscription, and per-tenant audit-log — every mutating one writes an audit row in the same transaction, reason is a required field (422 without one). Downgrade-impact *reporting* before a plan change is explicitly left to Stage 13 — today a downgrade is allowed and data is preserved, with `check_limit` naturally blocking new creates past the lower cap. 16 new tests, 92/93 backend total (1 pre-existing unrelated). Dev platform admin seeded (`app/seed_platform_admin.py`, env-var credentials with a loud dev-only fallback). **Frontend** (user's explicit choice: same Tauri client, not a separate web app): `client/src/platformAdmin/` — its own login screen (no shop-code field, no persisted session — a platform operator re-authenticates every launch by design), its own `ApiClient.platformAdminToken` completely separate from the tenant `token` field (mirrors the backend's two audiences; neither token is ever sent on the other's requests), and its own shell (`PlatformAdminApp.tsx`, visibly different header color/chrome, not another tab in `MainApp`'s `TabList`) with Dashboard and Tenants (list → detail, six action forms, audit log table). Reached via a "Platform admin sign in" link on the tenant `Login.tsx`. `tsc --noEmit` clean, 13/13 client tests. Live browser verification blocked by the same Tauri-IPC limitation as every frontend stage since Stage 8 — not re-attempted. **Follow-up fix:** a real gap was found post-ship — an upgrade request only ever surfaced if an admin happened to open that exact tenant and manually change its plan; there was no cross-tenant inbox. Added `GET /platform-admin/upgrade-requests` (defaults to pending only, `include_decided=true` for history), `POST .../upgrade-requests/{id}/approve` (delegates straight to `change_plan` — same downgrade-impact `confirm` gate, same audit trail, no duplicated logic) and `.../reject`, a `pending_upgrade_requests` dashboard stat, and a new "Upgrade requests" tab (`PlatformAdminUpgradeRequests.tsx`) with per-row approve/reject dialogs. 7 new backend tests. **Two more follow-up fixes:** (1) `change_plan` updated `Tenant.active_plan_id` but never touched the existing `Subscription.annual_amc` — `ensure_subscription` only sets pricing once, at first creation, so a tenant's displayed AMC stayed frozen at whatever plan it started on forever (reported as "AMC always shows ₹90,000" after upgrading off Essential). Fixed: `change_plan` now updates the current subscription's `annual_amc` to the new plan's; `setup_fee` is deliberately left untouched (one-time historical charge, not tied to the current plan). (2) Added `POST /tenants/{id}/revoke-plan` — clears `active_plan_id` entirely, distinct from `suspend` (login still works; every plan-gated feature just fails closed). This exposed a real crash: `check_limit()` raised a bare `ValueError` for a tenant with no active plan, unhandled by the one call site with no `require_feature` gate in front of it (`POST /users` — Section 11.5, base user management isn't a catalog feature) — every other router is protected because `require_feature` already 403s before `check_limit` is ever reached. Fixed with a `NO_ACTIVE_PLAN` structured 403 in `check_limit` itself. Frontend: a "Revoke plan" action card next to Change Plan on the tenant detail screen. 5 new tests (`tests/test_revoke_plan.py`), 123/124 backend total (1 pre-existing unrelated). |
| 12 | Feature/limit override UI + audit log table + service | **Done — folded into Stage 11** — `services/platform_audit.py`, `platform_audit_log` table, and the Feature override/Limit override forms + audit-log table all shipped as part of Stage 11's tenant detail screen rather than as a separate pass, since they're the same actions on the same screen. |
| 13 | Plan change (upgrade/downgrade) logic + downgrade-impact check | **Done** — `services/plan_change.py::assess_plan_change_impact` computes exceeded limits and lost features for a hypothetical plan switch, respecting existing `TenantFeatureOverride`/`TenantLimitOverride` rows exactly as `can_use_feature`/`check_limit` do (an override survives a plan change). New `GET .../plan-change-impact` preview endpoint; `POST .../change-plan` now requires `confirm: true` when the impact is non-empty, otherwise 409s with the impact payload attached — so a downgrade can never be applied without the operator having seen what it costs. A confirmed impact is recorded in the audit row's `new_value` for the permanent record. Frontend: the Change Plan form runs the impact check live as soon as a plan is picked, shows a warning card (exceeded limits + lost features) for anything non-empty, and gates the submit button behind an explicit "I understand" checkbox. 12 new backend tests, including two that prove the actual data-preservation claims end to end (6 users survive a forced-confirm downgrade to a 5-user-cap plan, with the 7th blocked; a product created pre-upgrade comes back byte-for-byte identical post-upgrade) — 99/100 backend total (1 pre-existing unrelated). `tsc --noEmit` clean, 13/13 client tests. Same Tauri-IPC browser-verification limit as every frontend stage since Stage 8. |
| 14 | Tests per 11.11 + security review | **Done** — audited every item in Section 11.11's test list against what actually exists. Filled the one real functional gap it exposed: the **subscription lifecycle state machine** (Section 11.8) had never actually been built — `services/subscription_lifecycle.py` (pure `resolve_subscription_status(renewal_date, today, window, grace)`, date-driven ACTIVE→EXPIRING→EXPIRED→GRACE_PERIOD→SUSPENDED, configurable via new `settings.subscription_expiring_window_days`/`subscription_grace_period_days`) plus `sync_subscription_status`, called from both `POST /auth/login` and `get_current_user` so the transition takes effect on a tenant's very next request/login, not on some batch job's schedule. Never regresses an already-suspended tenant (manual or auto) back to active — only `extend-subscription`/`reactivate` do that; `extend-subscription` was fixed to also clear `Tenant.status` if the auto-cutoff had fired, since it hadn't needed to before this stage existed. 12 new tests, including a full login-blocked-then-restored-by-extend round trip. Two items from 11.11 are honestly not coverable in this app as it stands and are documented rather than faked: an Enterprise-*only* live endpoint gate (proven instead at the `require_feature` dependency level in `test_entitlements.py`, since no Enterprise-exclusive router exists — see Section 11.1's module gaps) and the warehouse 2nd/3rd-item limit test (no warehouse module exists at all). `FeatureGate` hide/lock/disable render-testing was re-attempted directly against `FluentProvider` itself (not just a screen) and confirmed to hit the exact same `tabster`/Vitest module-resolution failure documented in Phase 8 — this is a repo-wide Vitest/Fluent incompatibility, not something scoped to admin screens; logic-only coverage (`resolveFeature`) stands in for it. **Security review** (via the `security-review` skill, two-stage identify-then-filter): one candidate finding — `services/stock_ledger.py::record_movement`'s idempotency lookup used a bare `session.get(StockMovement, id)` with no tenant filter, inconsistent with the identical idempotency pattern in `services/sales.py` (`get_tenant_owned`). Filtered out as not actionable (2/10 confidence) because the only attack path requires guessing another tenant's unguessable UUIDv4 idempotency key with no oracle anywhere in the app to shortcut it — but fixed anyway since it's a one-line, zero-risk consistency fix now scoped by `get_tenant_owned` like everywhere else. Full suite: 111/112 backend passing (1 pre-existing, unrelated to this project — a macOS system-library gap in WeasyPrint), 13/13 client. |

Stages 2+ build **on top of** the schema from Stage 1 but require deciding,
before writing code, which of the missing modules (11.1) get built now vs.
deferred — that's a scope call for whoever's driving next, not something to
infer silently.

### 11.13 Platform Super Admin — design note

Separate `platform_admins` table and separate JWT audience/issuer (or a
distinct `aud` claim) from tenant `users` — never reuse `UserRole.admin`.
Platform admin actions (change plan, override feature/limit, suspend/
reactivate tenant, extend subscription) each write a `platform_audit_log`
row: who, when, action, tenant_id, old_value, new_value, reason. Design
this table in Stage 11, not Stage 1, since it has no bearing on tenant-side
schema.
