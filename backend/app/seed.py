"""Seed a realistic test dataset: a tenant, users, suppliers, customers, a
spare-parts catalog across categories, initial stock, and a spread of sample
sales over the last 30 days (so reports/dashboard have something to show).

Run: uv run python -m app.seed
"""

import random
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlmodel import Session, select

from app.auth.security import hash_password
from app.db import engine
from app.models import (
    Barcode,
    Customer,
    Plan,
    Product,
    Supplier,
    Tenant,
    User,
    UserRole,
)
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

# (sku, name, oem_part_number, category, subcategory, brand, compatible_models,
#  warehouse, rack, bin_location, supplier_name, supplier_code, lead_time_days,
#  min_order_qty, cost, sale, gst_percent, reorder_threshold, safety_stock,
#  max_stock, critical_part, initial_qty, box_pack_qty|None)
PRODUCTS = [
    dict(sku="FST-M10-BOLT", name="M10 Hex Bolt", oem_part_number="STD-M10-BOLT", category="fasteners",
         subcategory="Bolt", brand="Generic", compatible_models="MX-200,MX-300",
         warehouse="WH-01", rack="F-01", bin_location="B-01", supplier_name="Bharat Fasteners Co",
         supplier_code="SUP-002", lead_time_days=3, min_order_qty=100, cost="3.50", sale="5.00",
         gst_percent=Decimal(18), reorder_threshold=200, safety_stock=100, max_stock=2000,
         critical_part=False, initial_qty=1500, box_pack_qty=100),
    dict(sku="FST-M12-NUT", name="M12 Hex Nut", oem_part_number="STD-M12-NUT", category="fasteners",
         subcategory="Nut", brand="Generic", compatible_models="MX-200,MX-300,MX-400",
         warehouse="WH-01", rack="F-01", bin_location="B-02", supplier_name="Bharat Fasteners Co",
         supplier_code="SUP-002", lead_time_days=3, min_order_qty=100, cost="1.20", sale="2.00",
         gst_percent=Decimal(18), reorder_threshold=300, safety_stock=150, max_stock=3000,
         critical_part=False, initial_qty=2000, box_pack_qty=100),
    dict(sku="FST-WASH-10", name="Flat Washer 10mm", oem_part_number="STD-M10-WASH", category="fasteners",
         subcategory="Washer", brand="Generic", compatible_models="MX-200,MX-300",
         warehouse="WH-01", rack="F-01", bin_location="B-10", supplier_name="Bharat Fasteners Co",
         supplier_code="SUP-002", lead_time_days=3, min_order_qty=100, cost="0.40", sale="0.80",
         gst_percent=Decimal(18), reorder_threshold=500, safety_stock=200, max_stock=5000,
         critical_part=False, initial_qty=3000, box_pack_qty=100),
    dict(sku="HYD-FLT-100", name="Hydraulic Return Filter", oem_part_number="MAN-HRF-001", category="hydraulics",
         subcategory="Hydraulic Filter", brand="Manitou", compatible_models="MX-300",
         warehouse="WH-01", rack="H-01", bin_location="B-01", supplier_name="Apex Hydraulics Pvt Ltd",
         supplier_code="SUP-001", lead_time_days=7, min_order_qty=1, cost="450.00", sale="650.00",
         gst_percent=Decimal(18), reorder_threshold=5, safety_stock=3, max_stock=50,
         critical_part=False, initial_qty=40, box_pack_qty=None),
    dict(sku="HYD-FLT-OIL", name="Hydraulic Oil Filter Cartridge", oem_part_number="MAN-HOF-001",
         category="hydraulics", subcategory="Hydraulic Filter", brand="Manitou",
         compatible_models="MX-200,MX-300", warehouse="WH-01", rack="H-02", bin_location="B-01",
         supplier_name="Apex Hydraulics Pvt Ltd", supplier_code="SUP-001", lead_time_days=7,
         min_order_qty=1, cost="320.00", sale="480.00", gst_percent=Decimal(18),
         reorder_threshold=8, safety_stock=4, max_stock=50, critical_part=True, initial_qty=30,
         box_pack_qty=None),
    dict(sku="HYD-HOSE-12", name="Hydraulic Hose 1/2in (per m)", oem_part_number="HYD-12-001",
         category="hydraulics", subcategory="Hydraulic Hose", brand="Generic",
         compatible_models="MX-300,MX-400", warehouse="WH-01", rack="H-01", bin_location="R-01",
         supplier_name="Apex Hydraulics Pvt Ltd", supplier_code="SUP-001", lead_time_days=5,
         min_order_qty=10, cost="180.00", sale="270.00", gst_percent=Decimal(18),
         reorder_threshold=20, safety_stock=10, max_stock=200, critical_part=True, initial_qty=100,
         box_pack_qty=None),
    dict(sku="FLT-AIR-01", name="Air Filter Element", oem_part_number="Manitou 563416", category="filters",
         subcategory="Air Filter", brand="Manitou", compatible_models="MX-200,MX-300,MX-400",
         warehouse="WH-01", rack="A-01", bin_location="B-01", supplier_name="Apex Hydraulics Pvt Ltd",
         supplier_code="SUP-001", lead_time_days=7, min_order_qty=1, cost="560.00", sale="820.00",
         gst_percent=Decimal(18), reorder_threshold=6, safety_stock=3, max_stock=40,
         critical_part=False, initial_qty=25, box_pack_qty=None),
    dict(sku="FLT-FUEL-01", name="Fuel Filter", oem_part_number="Manitou 706498", category="filters",
         subcategory="Fuel Filter", brand="Manitou", compatible_models="MX-300,MX-400",
         warehouse="WH-01", rack="A-03", bin_location="B-02", supplier_name="Apex Hydraulics Pvt Ltd",
         supplier_code="SUP-001", lead_time_days=7, min_order_qty=1, cost="210.00", sale="320.00",
         gst_percent=Decimal(18), reorder_threshold=10, safety_stock=5, max_stock=60,
         critical_part=True, initial_qty=45, box_pack_qty=None),
    dict(sku="FLT-CABIN-01", name="Cabin Air Filter", oem_part_number="Manitou 525523", category="filters",
         subcategory="Cabin Filter", brand="Manitou", compatible_models="MX-400",
         warehouse="WH-01", rack="A-02", bin_location="B-01", supplier_name="Apex Hydraulics Pvt Ltd",
         supplier_code="SUP-001", lead_time_days=7, min_order_qty=1, cost="150.00", sale="230.00",
         gst_percent=Decimal(18), reorder_threshold=8, safety_stock=4, max_stock=30,
         critical_part=False, initial_qty=20, box_pack_qty=None),
    dict(sku="ELE-ALT-90A", name="Alternator 90A", oem_part_number="Manitou 746120", category="electrical",
         subcategory="Alternator", brand="Manitou", compatible_models="MX-300,MX-400",
         warehouse="WH-01", rack="E-02", bin_location="B-03", supplier_name="ABC Auto Electricals",
         supplier_code="SUP-003", lead_time_days=10, min_order_qty=1, cost="4200.00", sale="5800.00",
         gst_percent=Decimal(18), reorder_threshold=3, safety_stock=2, max_stock=10,
         critical_part=True, initial_qty=3, box_pack_qty=None),
    dict(sku="ELE-STARTER-01", name="Starter Motor", oem_part_number="MAN-START-001", category="electrical",
         subcategory="Starter Motor", brand="Manitou", compatible_models="MX-200,MX-300",
         warehouse="WH-01", rack="E-04", bin_location="B-02", supplier_name="ABC Auto Electricals",
         supplier_code="SUP-003", lead_time_days=10, min_order_qty=1, cost="5100.00", sale="6900.00",
         gst_percent=Decimal(18), reorder_threshold=3, safety_stock=2, max_stock=10,
         critical_part=True, initial_qty=4, box_pack_qty=None),
    dict(sku="ELE-HEADLIGHT-LED", name="Headlight Assembly LED", oem_part_number="MAN-HL-LED-01",
         category="electrical", subcategory="Lighting", brand="Manitou", compatible_models="MX-400",
         warehouse="WH-01", rack="E-03", bin_location="B-01", supplier_name="ABC Auto Electricals",
         supplier_code="SUP-003", lead_time_days=10, min_order_qty=1, cost="1350.00", sale="1950.00",
         gst_percent=Decimal(18), reorder_threshold=6, safety_stock=3, max_stock=25,
         critical_part=False, initial_qty=18, box_pack_qty=None),
    dict(sku="UND-ROLLER-01", name="Track Roller", oem_part_number="MAN-TRK-ROLL-01", category="undercarriage",
         subcategory="Track Roller", brand="Manitou", compatible_models="MX-400",
         warehouse="WH-01", rack="U-01", bin_location="B-01", supplier_name="SteelTrack Undercarriage Supplies",
         supplier_code="SUP-004", lead_time_days=14, min_order_qty=1, cost="2200.00", sale="3100.00",
         gst_percent=Decimal(18), reorder_threshold=4, safety_stock=2, max_stock=20,
         critical_part=True, initial_qty=12, box_pack_qty=None),
    dict(sku="UND-CHAIN-LINK", name="Track Chain Link", oem_part_number="MAN-TRK-CHAIN-01",
         category="undercarriage", subcategory="Track Chain", brand="Manitou", compatible_models="MX-400",
         warehouse="WH-01", rack="U-01", bin_location="B-02", supplier_name="SteelTrack Undercarriage Supplies",
         supplier_code="SUP-004", lead_time_days=14, min_order_qty=10, cost="340.00", sale="500.00",
         gst_percent=Decimal(18), reorder_threshold=15, safety_stock=8, max_stock=100,
         critical_part=True, initial_qty=60, box_pack_qty=None),
    dict(sku="ENG-SEAL-KIT", name="Engine Oil Seal Kit", oem_part_number="MAN-OSK-001", category="engine",
         subcategory="Seal Kit", brand="OEM", compatible_models="MX-200,MX-300,MX-400",
         warehouse="WH-01", rack="C-01", bin_location="B-02", supplier_name="Industrial Engine Spares",
         supplier_code="SUP-005", lead_time_days=12, min_order_qty=1, cost="780.00", sale="1150.00",
         gst_percent=Decimal(18), reorder_threshold=6, safety_stock=3, max_stock=30,
         critical_part=True, initial_qty=20, box_pack_qty=None),
    dict(sku="ENG-PISTON-RING", name="Piston Ring Set", oem_part_number="MAN-PR-001", category="engine",
         subcategory="Piston Ring", brand="OEM", compatible_models="MX-300",
         warehouse="WH-01", rack="C-02", bin_location="B-01", supplier_name="Industrial Engine Spares",
         supplier_code="SUP-005", lead_time_days=12, min_order_qty=1, cost="1650.00", sale="2400.00",
         gst_percent=Decimal(18), reorder_threshold=4, safety_stock=2, max_stock=20,
         critical_part=True, initial_qty=10, box_pack_qty=None),
    dict(sku="ATT-FORK-1200", name="Forklift Fork 1200mm", oem_part_number="MAN-FORK-1200",
         category="attachments", subcategory="Fork", brand="Manitou", compatible_models="MX-200",
         warehouse="WH-01", rack="YARD-01", bin_location="F-01", supplier_name="Manitou Attachments",
         supplier_code="SUP-006", lead_time_days=21, min_order_qty=1, cost="3800.00", sale="5400.00",
         gst_percent=Decimal(18), reorder_threshold=4, safety_stock=2, max_stock=15,
         critical_part=True, initial_qty=10, box_pack_qty=None),
    dict(sku="TIRE-28X9-15", name="Solid Tire 28x9-15", oem_part_number="TYRE-28X9-15", category="tires",
         subcategory="Solid Tire", brand="OEM", compatible_models="MX-200",
         warehouse="WH-01", rack="TYRE-01", bin_location="T-02", supplier_name="Industrial Tyres India",
         supplier_code="SUP-007", lead_time_days=14, min_order_qty=1, cost="6200.00", sale="8600.00",
         gst_percent=Decimal(18), reorder_threshold=3, safety_stock=2, max_stock=15,
         critical_part=True, initial_qty=8, box_pack_qty=None),
]

SUPPLIERS = [
    ("Apex Hydraulics Pvt Ltd", "9876500011", "sales@apexhydraulics.example", "27AAAPA1111A1Z5"),
    ("Bharat Fasteners Co", "9876500022", "orders@bharatfasteners.example", "27AAAPB2222B1Z5"),
    ("SteelTrack Undercarriage Supplies", "9876500033", "info@steeltrack.example", "27AAAPS3333C1Z5"),
    ("ABC Auto Electricals", "9876500044", "sales@abcauto.example", "27AAABC4444F1Z5"),
    ("Industrial Engine Spares", "9876500055", "orders@indengspares.example", "27AAAIES5555G1Z5"),
    ("Manitou Attachments", "9876500066", "sales@manitouatt.example", "27AAAMAN6666H1Z5"),
    ("Industrial Tyres India", "9876500077", "sales@indtyres.example", "27AAAITI7777I1Z5"),
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
            company_name="Manitou Spare Parts",
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
        for i, p in enumerate(PRODUCTS):
            product = Product(
                tenant_id=tenant.id,
                sku=p["sku"],
                name=p["name"],
                oem_part_number=p["oem_part_number"],
                category=p["category"],
                subcategory=p["subcategory"],
                brand=p["brand"],
                compatible_models=p["compatible_models"],
                base_unit="piece",
                warehouse=p["warehouse"],
                rack=p["rack"],
                bin_location=p["bin_location"],
                supplier_name=p["supplier_name"],
                supplier_code=p["supplier_code"],
                lead_time_days=p["lead_time_days"],
                min_order_qty=p["min_order_qty"],
                cost_price=Decimal(p["cost"]),
                sale_price=Decimal(p["sale"]),
                gst_percent=p["gst_percent"],
                reorder_threshold=p["reorder_threshold"],
                safety_stock=p["safety_stock"],
                max_stock=p["max_stock"],
                critical_part=p["critical_part"],
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
            barcodes_by_product[p["sku"]] = [single]
            if p["box_pack_qty"]:
                box = Barcode(
                    tenant_id=tenant.id,
                    product_id=product.id,
                    barcode_value=f"89000000{i:04d}2",
                    pack_qty=p["box_pack_qty"],
                    label=f"Box of {p['box_pack_qty']}",
                )
                session.add(box)
                barcodes_by_product[p["sku"]].append(box)
        session.commit()

        # initial stock via the ledger service, not raw inserts, so balances
        # stay consistent with everything else in the system
        now = datetime.now(UTC)
        for product, p in zip(products, PRODUCTS):
            # a few products intentionally received below their reorder
            # threshold, so low-stock reporting has something to show
            receive_qty = max(0, p["reorder_threshold"] - 2) if p["sku"] in LOW_STOCK_OVERRIDES else p["initial_qty"]
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
                    gst_amount=Decimal(0),
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
