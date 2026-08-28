"""Seed a realistic test dataset: a tenant, users, suppliers, customers, a
spare-parts catalog across categories, initial stock, and a spread of sample
sales over the last 30 days (so reports/dashboard have something to show).

Run: uv run python -m app.seed
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlmodel import Session, select

from app.auth.security import hash_password
from app.db import engine
from app.models import Barcode, Customer, Plan, Product, Supplier, Tenant, User, UserRole
from app.models.stock_movement import MovementType
from app.schemas.sale import SaleCreate, SaleItemCreate
from app.services.sales import create_sale
from app.services.stock_ledger import record_movement
from app.services.subscriptions import ensure_subscription

random.seed(42)  # deterministic seed data across runs

TERMINAL_ID = "SEED"
INVOICE_SERIES = "SEED"  # distinct from any real terminal (T1, T2, ...) so a client's own
# local invoice counter — which starts fresh at 1001 per series — never collides with seed data

TENANT_CODE = "MONITOU-001"  # same tenant_code the tenant_id backfill migration assigned
# existing (pre-tenancy) data to — see alembic/versions/4c4b99b6eb8b

# (sku, name, category, compatible_models, cost, sale, reorder_threshold, initial_qty, box_pack_qty|None)
PRODUCTS = [
    ("FST-M10-BOLT", "M10 Hex Bolt", "fasteners", "MX-200,MX-300", "3.50", "5.00", 200, 1500, 100),
    ("FST-M12-NUT", "M12 Hex Nut", "fasteners", "MX-200,MX-300,MX-400", "1.20", "2.00", 300, 2000, 100),
    ("FST-WASH-10", "Flat Washer 10mm", "fasteners", "MX-200,MX-300", "0.40", "0.80", 500, 3000, 100),
    ("HYD-FLT-100", "Hydraulic Return Filter", "hydraulics", "MX-300", "450.00", "650.00", 5, 40, None),
    ("HYD-FLT-OIL", "Hydraulic Oil Filter Cartridge", "hydraulics", "MX-200,MX-300", "320.00", "480.00", 8, 30, None),
    ("HYD-HOSE-12", "Hydraulic Hose 1/2in (per m)", "hydraulics", "MX-300,MX-400", "180.00", "270.00", 20, 100, None),
    ("FLT-AIR-01", "Air Filter Element", "filters", "MX-200,MX-300,MX-400", "560.00", "820.00", 6, 25, None),
    ("FLT-FUEL-01", "Fuel Filter", "filters", "MX-300,MX-400", "210.00", "320.00", 10, 45, None),
    ("FLT-CABIN-01", "Cabin Air Filter", "filters", "MX-400", "150.00", "230.00", 8, 20, None),
    ("ELE-ALT-90A", "Alternator 90A", "electrical", "MX-300,MX-400", "4200.00", "5800.00", 3, 3, None),
    ("ELE-STARTER-01", "Starter Motor", "electrical", "MX-200,MX-300", "5100.00", "6900.00", 3, 4, None),
    ("ELE-HEADLIGHT-LED", "Headlight Assembly LED", "electrical", "MX-400", "1350.00", "1950.00", 6, 18, None),
    ("UND-ROLLER-01", "Track Roller", "undercarriage", "MX-400", "2200.00", "3100.00", 4, 12, None),
    ("UND-CHAIN-LINK", "Track Chain Link", "undercarriage", "MX-400", "340.00", "500.00", 15, 60, None),
    ("ENG-SEAL-KIT", "Engine Oil Seal Kit", "engine", "MX-200,MX-300,MX-400", "780.00", "1150.00", 6, 20, None),
    ("ENG-PISTON-RING", "Piston Ring Set", "engine", "MX-300", "1650.00", "2400.00", 4, 10, None),
    ("ATT-FORK-1200", "Forklift Fork 1200mm", "attachments", "MX-200", "3800.00", "5400.00", 4, 10, None),
    ("TIRE-28X9-15", "Solid Tire 28x9-15", "tires", "MX-200", "6200.00", "8600.00", 3, 8, None),
]

SUPPLIERS = [
    ("Apex Hydraulics Pvt Ltd", "9876500011", "sales@apexhydraulics.example", "27AAAPA1111A1Z5"),
    ("Bharat Fasteners Co", "9876500022", "orders@bharatfasteners.example", "27AAAPB2222B1Z5"),
    ("SteelTrack Undercarriage Supplies", "9876500033", "info@steeltrack.example", "27AAAPS3333C1Z5"),
]

CUSTOMERS = [
    ("Konkan Construction Pvt Ltd", "9876511111", "accounts@konkanconstruction.example", "27AAACK4444D1Z5"),
    ("Odisha Earthmovers", "9876522222", "purchase@odishaearthmovers.example", "21AAACO5555E1Z5"),
]

PAYMENT_MODES = ["cash", "card", "upi"]

# products intentionally left below reorder_threshold so /reports/low-stock-alerts
# and the digest job have something to show without depending on random sales
LOW_STOCK_OVERRIDES = {"ELE-ALT-90A", "ELE-STARTER-01", "TIRE-28X9-15"}


def _get_or_create_tenant(session: Session) -> Tenant:
    # ESSENTIAL is the recommended/default commercial package — see
    # CLAUDE.md Section 11.5. Run `uv run python -m app.seed_plans` first so
    # this plan row exists.
    essential = session.exec(select(Plan).where(Plan.code == "ESSENTIAL")).first()

    tenant = session.exec(select(Tenant).where(Tenant.tenant_code == TENANT_CODE)).first()
    if tenant is None:
        tenant = Tenant(
            tenant_code=TENANT_CODE,
            company_name="Monitou Spare Parts",
            active_plan_id=essential.id if essential else None,
        )
        session.add(tenant)
        session.commit()
        session.refresh(tenant)

    if essential:
        ensure_subscription(session, tenant, essential)  # idempotent — no-op if one already exists
    return tenant


def seed() -> None:
    with Session(engine) as session:
        tenant = _get_or_create_tenant(session)

        # RLS (migration 9196eb11b8d2) forces every write on a business
        # table to satisfy `tenant_id = current_setting('app.tenant_id')`.
        # A plain `SET` (not `SET LOCAL`) is deliberate here — unlike the
        # request path (`tenancy.set_rls_tenant`, transaction-scoped so a
        # pooled connection can't carry it into someone else's request),
        # this script owns its connection for its whole run and commits
        # repeatedly, so the setting needs to survive across commits.
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text(f"SET app.tenant_id = '{tenant.id}'"))

        if session.exec(select(Product).where(Product.tenant_id == tenant.id)).first():
            print("already seeded, skipping")
            return

        admin = User(
            tenant_id=tenant.id, username="admin1", password_hash=hash_password("adminpass"), role=UserRole.admin
        )
        cashier = User(
            tenant_id=tenant.id, username="sales1", password_hash=hash_password("salespass"), role=UserRole.sales
        )
        session.add_all([admin, cashier])
        session.commit()
        session.refresh(admin)
        session.refresh(cashier)

        session.add_all(
            Supplier(tenant_id=tenant.id, name=name, phone=phone, email=email, gstin=gstin)
            for name, phone, email, gstin in SUPPLIERS
        )
        session.add_all(
            Customer(tenant_id=tenant.id, name=name, phone=phone, email=email, gstin=gstin)
            for name, phone, email, gstin in CUSTOMERS
        )
        session.commit()

        products: list[Product] = []
        barcodes_by_product: dict[str, list[Barcode]] = {}
        for i, (sku, name, category, models, cost, sale, threshold, qty, box_pack) in enumerate(PRODUCTS):
            product = Product(
                tenant_id=tenant.id,
                sku=sku,
                name=name,
                category=category,
                compatible_models=models,
                base_unit="piece",
                cost_price=Decimal(cost),
                sale_price=Decimal(sale),
                reorder_threshold=threshold,
            )
            session.add(product)
            session.commit()
            session.refresh(product)
            products.append(product)

            single = Barcode(
                tenant_id=tenant.id,
                product_id=product.id,
                barcode_value=f"89000000{i:04d}1",
                pack_qty=1,
                label="Single piece",
            )
            session.add(single)
            barcodes_by_product[sku] = [single]
            if box_pack:
                box = Barcode(
                    tenant_id=tenant.id,
                    product_id=product.id,
                    barcode_value=f"89000000{i:04d}2",
                    pack_qty=box_pack,
                    label=f"Box of {box_pack}",
                )
                session.add(box)
                barcodes_by_product[sku].append(box)
        session.commit()

        # initial stock via the ledger service, not raw inserts, so balances
        # stay consistent with everything else in the system
        now = datetime.now(timezone.utc)
        for product, row in zip(products, PRODUCTS):
            sku, _name, _cat, _models, _cost, _sale, threshold, qty, _box = row
            # a few products intentionally received below their reorder
            # threshold, so low-stock reporting has something to show
            receive_qty = max(0, threshold - 2) if sku in LOW_STOCK_OVERRIDES else qty
            record_movement(
                session,
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                product_id=product.id,
                qty_base_units=receive_qty,
                movement_type=MovementType.purchase,
                terminal_id=TERMINAL_ID,
                created_at_client=now - timedelta(days=35),
            )

        # sample sales spread over the last 30 days — skip the products
        # deliberately understocked above, so their balance stays a clean
        # demonstration of "below threshold" instead of going deeply negative
        sellable_products = [p for p in products if p.sku not in LOW_STOCK_OVERRIDES]
        invoice_seq = 1000
        sale_count = 0
        for day_offset in range(30, 0, -1):
            day = now - timedelta(days=day_offset)
            for _ in range(random.randint(0, 4)):
                product = random.choice(sellable_products)
                barcode = random.choice(barcodes_by_product[product.sku])
                qty_base_units = random.randint(1, 3) * barcode.pack_qty
                invoice_seq += 1
                sale_time = day.replace(
                    hour=random.randint(9, 18), minute=random.randint(0, 59), second=0, microsecond=0
                )
                payload = SaleCreate(
                    id=uuid.uuid4(),
                    invoice_number=f"{INVOICE_SERIES}-{invoice_seq}",
                    invoice_series=INVOICE_SERIES,
                    terminal_id=TERMINAL_ID,
                    customer_id=None,
                    payment_mode=random.choice(PAYMENT_MODES),
                    gst_amount=Decimal("0"),
                    created_at_client=sale_time,
                    items=[
                        SaleItemCreate(
                            id=uuid.uuid4(),
                            product_id=product.id,
                            barcode_id=barcode.id,
                            qty_base_units=qty_base_units,
                            unit_price=product.sale_price,
                        )
                    ],
                )
                create_sale(session, payload, tenant_id=tenant.id, cashier_id=cashier.id)
                sale_count += 1

        print(
            f"seeded tenant {TENANT_CODE}, 2 users (admin1/adminpass, sales1/salespass), "
            f"{len(SUPPLIERS)} suppliers, {len(CUSTOMERS)} customers, "
            f"{len(products)} products, "
            f"{sum(len(b) for b in barcodes_by_product.values())} barcodes, "
            f"{sale_count} sample sales"
        )


if __name__ == "__main__":
    seed()
