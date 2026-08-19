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
