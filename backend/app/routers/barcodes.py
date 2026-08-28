from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, or_, select

from app.auth.deps import get_current_user, require_role
from app.db import get_session
from app.models.barcode import Barcode
from app.models.product import Product
from app.models.user import User, UserRole
from app.schemas.barcode import BarcodeCreate, BarcodeRead, BarcodeScanResult
from app.services.entitlements import require_feature
from app.tenancy import get_tenant_owned

router = APIRouter(prefix="/barcodes", tags=["barcodes"])


def _to_scan_result(barcode: Barcode, product: Product) -> BarcodeScanResult:
    return BarcodeScanResult(
        barcode=BarcodeRead.model_validate(barcode, from_attributes=True),
        product_id=product.id,
        product_sku=product.sku,
        product_name=product.name,
        base_units_per_scan=barcode.pack_qty,
        sale_price=product.sale_price,
    )


@router.post("", response_model=BarcodeRead, status_code=status.HTTP_201_CREATED)
async def create_barcode(
    payload: BarcodeCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    # BARCODE_GENERATION (Essential+) gates *creating* a new barcode/pack-size
    # mapping for the catalog — an admin catalog-management capability. It
    # does not gate scanning an existing one during checkout (below); that's
    # core to BASIC_SALES_ORDER, which every plan has. See CLAUDE.md
    # Section 11 Stage 5 for why the line is drawn here.
    _feature: None = Depends(require_feature("BARCODE_GENERATION")),
) -> Barcode:
    if get_tenant_owned(session, Product, payload.product_id, admin.tenant_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    exists = session.exec(
        select(Barcode).where(
            Barcode.tenant_id == admin.tenant_id, Barcode.barcode_value == payload.barcode_value
        )
    ).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="barcode already exists")
    barcode = Barcode(tenant_id=admin.tenant_id, **payload.model_dump())
    session.add(barcode)
    session.commit()
    session.refresh(barcode)
    return barcode


@router.get("/search", response_model=list[BarcodeScanResult])
async def search_barcodes(
    q: str = Query(..., min_length=1),
    limit: int = Query(8, ge=1, le=50),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    _feature: None = Depends(require_feature("BASIC_SALES_ORDER")),
) -> list[BarcodeScanResult]:
    """Live search for POS billing — matches barcode value, SKU, or product
    name in one query, ranked so an exact barcode/SKU match wins, then a
    prefix match, then any substring match. This is the server-side
    replacement for what used to be a local SQLite cache query."""
    pattern = f"%{q}%"
    prefix = f"{q}%"
    rows = session.exec(
        select(Barcode, Product)
        .join(Product, Product.id == Barcode.product_id)
        .where(
            Barcode.tenant_id == user.tenant_id,
            Product.tenant_id == user.tenant_id,
            Product.is_active == True,  # noqa: E712
            or_(
                Barcode.barcode_value.ilike(pattern),
                Product.sku.ilike(pattern),
                Product.name.ilike(pattern),
            ),
        )
        .order_by(
            (Barcode.barcode_value == q).desc(),
            (Product.sku == q).desc(),
            (Product.sku.ilike(prefix)).desc(),
            (Product.name.ilike(prefix)).desc(),
            Product.name,
        )
        .limit(limit)
    ).all()
    return [_to_scan_result(barcode, product) for barcode, product in rows]


@router.get("/{barcode_value}", response_model=BarcodeScanResult)
async def scan_barcode(
    barcode_value: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    _feature: None = Depends(require_feature("BASIC_SALES_ORDER")),
) -> BarcodeScanResult:
    """Resolve a scanned barcode to its product and base-unit multiplier (pack_qty)."""
    barcode = session.exec(
        select(Barcode).where(Barcode.tenant_id == user.tenant_id, Barcode.barcode_value == barcode_value)
    ).first()
    if barcode is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="barcode not found")
    product = get_tenant_owned(session, Product, barcode.product_id, user.tenant_id)
    if product is None or not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    return _to_scan_result(barcode, product)
