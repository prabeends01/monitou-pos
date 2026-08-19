# Monitou POS

A retail point-of-sale and inventory management system for a shop selling
spare parts for handling, lifting, and earthmoving equipment.

Two apps share one backend:
- **Backend** — FastAPI + PostgreSQL REST API
- **Client** — a Windows desktop POS app (Tauri + React), installed on shop
  terminals, talking directly to the backend over HTTPS

For the full build history, data model, and open design decisions, see
[`CLAUDE.md`](./CLAUDE.md) — this README is the practical "what is this and
how do I run it" entry point.

---

## Features

- **Auth & roles** — JWT login, two roles: `admin` (full access — catalog,
  stock, users, reports, costs) and `sales` (search/scan, create sales,
  print invoices, view only their own sales history)
- **Product catalog** — SKU, category, compatible equipment models, and
  **multiple barcodes per product** for different pack sizes (a part can be
  bought/sold loose or as a sealed box of 50/100+, each with its own
  barcode; stock always resolves to a single base-unit count)
- **Live search** — POS billing searches barcode value, SKU, and product
  name together as you type, with ranked suggestions (exact match first,
  then prefix, then substring)
- **Append-only stock ledger** — every stock change (sale, purchase,
  adjustment, stock-take) is a new row, never an edited counter; current
  stock is the sum of movements for that product. Idempotent by a
  client-generated ID, so a retried request after a dropped connection is a
  safe no-op, not a double-counted sale.
- **Editable quantities** — scanning a box barcode defaults the cart line to
  its full pack size (e.g. 100), but the cashier can edit it down for a
  partial sale from an already-opened box
- **GST-compliant invoicing** — sequential invoice numbers per terminal
  series, server-assigned; GST invoice PDFs generated on demand
- **Receipt printing** — ESC/POS thermal printer support over the network
  (TCP), triggered straight from the POS screen
- **Admin reporting** — sales summary (daily/weekly/monthly, charted),
  stock-value and stock-health stats, low-stock alerts, plus a scheduled
  digest job so low stock doesn't require someone to open the app to notice
- **Role enforcement is server-side, always** — every sensitive endpoint
  checks the JWT's role claim; the client UI hiding a button is a
  convenience, not the actual security boundary

---

## Architecture

```
┌─────────────────────┐         HTTPS          ┌──────────────────────┐
│  Windows POS client  │ ─────────────────────► │   FastAPI backend    │
│  (Tauri + React)     │ ◄───────────────────── │                       │
└─────────────────────┘        JSON/REST         └──────────┬───────────┘
                                                              │
                                                              ▼
                                                   ┌──────────────────────┐
                                                   │   PostgreSQL          │
                                                   └──────────────────────┘
```

**Client-server, not client-database.** The desktop client never talks to
the database directly and never has DB credentials — every screen reads and
writes straight through the backend's REST API. There is **no local
database, no offline mode, and no background sync** on the client. This was
a deliberate simplification: an earlier version kept a local SQLite
cache/outbox on the client with a background sync worker for offline
support, but that repeatedly caused hard-to-debug data-integrity issues
(stale caches, invoice-number collisions between independently-numbering
terminals, cache conflicts after a data reset). Removing it in favor of
"always online, one source of truth" traded away offline capability for a
much simpler, more reliable system — see `CLAUDE.md` Section 1/4 for the
full reasoning. In practice this means shop PCs need a working connection to
the backend to sell anything; a failed request (network down, backend
unreachable) shows a visible error and leaves the cart intact for retry
rather than silently queuing.

### Backend

| | |
|---|---|
| Language / framework | Python 3.12, FastAPI |
| ORM | SQLModel (SQLAlchemy 2.0 + Pydantic v2) |
| Database | **PostgreSQL only** — no SQLite fallback anywhere in the app (pytest uses an in-memory SQLite fixture purely for fast, isolated tests — that's test infra, not an application datastore) |
| Migrations | Alembic |
| Auth | JWT (python-jose), bcrypt password hashing (passlib) |
| Scheduled jobs | APScheduler — low-stock digest |
| PDF generation | WeasyPrint — GST invoice PDFs |
| Package management | uv (no `requirements.txt`, no manually managed venvs) |
| Tests | pytest + httpx, 36 tests |

Key design points:
- Stock is an append-only ledger (`stock_movements`); current balance is
  derived, never stored/edited directly.
- Every mutating stock/sale write goes through `services/stock_ledger.py` —
  never directly from a router.
- Invoice numbers are **server-assigned**: `POST /sales`'s `invoice_number`
  is optional — when omitted, the server computes the next sequential
  number for that invoice series (max existing suffix + 1, with a small
  retry loop on the rare concurrent-collision case). This avoids any
  terminal needing to track its own counter.
- `GET /barcodes/search` — one ranked query across barcode value, SKU, and
  product name; the server-side foundation for the client's live search.
- Money fields are `Decimal`, never `float`. All timestamps stored in UTC.

### Client

| | |
|---|---|
| Shell | Tauri 2.x (Rust core, WebView2 on Windows) — small installer, low RAM use |
| UI | React 18 + TypeScript, Fluent UI v9 (Microsoft's Fluent 2 design system — the same visual language native Windows 11 apps use) |
| Server state | TanStack React Query — caching/retry/loading states for API calls |
| Local UI state | Zustand — cart contents, current screen; never server data, never persisted |
| Session | `@tauri-apps/plugin-store` — persists the JWT only, so the cashier isn't forced to log in every launch; not a data cache |
| HTTP | `@tauri-apps/plugin-http` — every request proxied through the Rust side, avoiding webview CORS restrictions |
| Charts | Recharts — admin dashboard sales chart |
| Printing | A Rust command (`src-tauri/src/printer.rs`) wrapping the `escpos` crate's `NetworkDriver` (TCP), invoked from the frontend |
| Packaging | Tauri's built-in bundler — produces a Windows MSI/NSIS installer directly |
| Tests | Vitest, 9 tests (cart/quantity logic) |

### Data model (high level)

`users` · `products` · `barcodes` (many-to-one with products, one per pack
size) · `stock_movements` (append-only ledger) · `sales` / `sale_items` ·
`suppliers` · `purchase_orders` / `purchase_order_items` · `customers`

Full column-level detail is in `CLAUDE.md` Section 5.

### Repository layout

```
monitou-pos/
├── backend/            # FastAPI app (Python, uv-managed)
│   ├── app/
│   │   ├── models/      # SQLModel table definitions
│   │   ├── schemas/     # Pydantic request/response models
│   │   ├── routers/     # HTTP endpoints
│   │   ├── services/    # business logic (stock ledger, invoicing, sales)
│   │   ├── auth/        # JWT + RBAC dependencies
│   │   └── jobs/        # scheduled low-stock digest
│   ├── alembic/         # migrations
│   └── tests/
├── client/              # Tauri + React desktop app (Node-managed)
│   ├── src-tauri/        # Rust shell, printer command, Tauri config
│   └── src/
│       ├── api/           # backend HTTP client
│       ├── screens/       # Login, POS Billing, Reports, Dashboard, admin screens
│       └── stores/        # Zustand (cart, session)
├── infra/docker/        # backend Dockerfile + entrypoint
├── docker-compose.yml   # local dev: Postgres + backend, one command
└── CLAUDE.md            # full architecture doc / build history
```

---

## Running on Windows

Two pieces to set up: the **backend** (runs once, centrally — not on every
POS terminal) and the **client** (installed on each shop PC/terminal).

### 1. Backend — via Docker

**Install Docker Desktop**
- Download from https://www.docker.com/products/docker-desktop/
- The installer will prompt for WSL2 if it's missing. To install it
  manually first: open PowerShell as Administrator, run `wsl --install`,
  then reboot.
- Launch Docker Desktop and wait until it reports "Docker is running".

**Get the code**
```powershell
git clone <your-repo-url> monitou-pos
cd monitou-pos
```

**Start Postgres + the backend**
```powershell
docker compose up -d --build
docker compose logs -f backend
```
The backend's entrypoint waits for the database, runs migrations
automatically, then starts the API — by the time `logs` shows uvicorn
running, it's ready. Press `Ctrl+C` to stop watching logs (the containers
keep running).

The API is now at `http://localhost:8000`. Postgres is exposed on host port
**5433** (not 5432 — avoids clashing with any Postgres already installed on
the machine).

**Seed test data**
```powershell
docker compose exec backend uv run python -m app.seed
```
Creates two test logins (`admin1`/`adminpass`, `sales1`/`salespass`), 18
sample products across categories with barcodes, and ~55 sample sales so
reports have something to show.

**Verify it's up**
```powershell
curl http://localhost:8000/health
```
Should return `{"status":"ok"}`.

**Day-to-day management**
```powershell
docker compose down        # stop, keep the data
docker compose down -v     # stop and wipe the database too
docker compose ps          # what's currently running
docker compose logs -f backend   # tail logs again
```

### 2. Client — build and install as a Windows app

**Install prerequisites**

| Tool | How |
|---|---|
| Rust | https://rustup.rs — download and run `rustup-init.exe`, accept defaults, restart your terminal afterward |
| Node.js (LTS) | https://nodejs.org, or `winget install OpenJS.NodeJS.LTS` |
| MSVC Build Tools | https://visualstudio.microsoft.com/visual-cpp-build-tools/ — run the installer and select the **"Desktop development with C++"** workload (Rust needs this to link on Windows) |
| WebView2 Runtime | Already present on Windows 10/11 (ships with Edge); the app installer prompts for it automatically if somehow missing |

**Configure the client**
```powershell
cd monitou-pos\client
copy .env.example .env
notepad .env
```
Set `VITE_API_BASE_URL`:
- Backend running on the same PC → leave it as `http://localhost:8000`
- Backend running elsewhere (a server, another machine) → point at that
  machine, e.g. `http://192.168.1.50:8000`

If the backend URL isn't `localhost:8000`/`127.0.0.1:8000`, also edit
`client\src-tauri\capabilities\default.json` and add the real URL to the
`http:default` permission's allow list — Tauri blocks requests to any host
not explicitly listed there:
```json
{
  "identifier": "http:default",
  "allow": [
    { "url": "http://localhost:8000/*" },
    { "url": "http://127.0.0.1:8000/*" },
    { "url": "http://192.168.1.50:8000/*" }
  ]
}
```

Optional — if this terminal has a network ESC/POS receipt printer, also set
`VITE_PRINTER_HOST` / `VITE_PRINTER_PORT` in `.env` before building (Vite
bakes env vars in at build time, so a later change needs a rebuild).

**Install dependencies and build**
```powershell
npm install
npm run tauri build
```
The first build compiles the full Rust toolchain and can take several
minutes. The installer lands at:
```
client\src-tauri\target\release\bundle\msi\Monitou POS_0.1.0_x64_en-US.msi
```
(or an NSIS `.exe` under `bundle\nsis\`, depending on the configured
bundle targets)

**Install and run**
- Double-click the `.msi` and click through the installer like any other
  Windows application
- Launch **"Monitou POS"** from the Start Menu
- Log in with `admin1`/`adminpass` or `sales1`/`salespass` (from the seed
  step above), or a real account created via the admin Products/Users flow

**Quick dev mode** (skip building an installer — for testing/iterating):
```powershell
cd monitou-pos\client
npm run tauri dev
```
Opens the app immediately in a window and hot-reloads on code changes.

---

## Running on macOS / Linux (development)

The same `docker compose up -d --build` backend steps work unchanged.

For the client, install Rust via `rustup` and Node via your usual method,
then `npm install` and `npm run tauri dev` from `client/`. On macOS, if you
also need GST invoice PDF generation working locally (WeasyPrint needs
native Pango/Cairo libraries), see the note in `CLAUDE.md` Section 6.

---

## Tests

```powershell
# backend
cd backend
uv run pytest

# client
cd client
npm test
```
