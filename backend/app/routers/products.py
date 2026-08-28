import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_role
from app.db import get_session
from app.models.product import Product
from app.models.user import User, UserRole
from app.schemas.product import ProductCreate, ProductRead, ProductReadPublic, ProductUpdate
from app.services.entitlements import require_feature
from app.services.usage_limits import check_limit, increment_usage
from app.tenancy import get_tenant_owned, tenant_scoped

router = APIRouter(prefix="/products", tags=["products"])


def _serialize(product: Product, user: User) -> ProductRead | ProductReadPublic:
    model = ProductRead if user.role == UserRole.admin else ProductReadPublic
    return model.model_validate(product, from_attributes=True)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("PRODUCT_MASTER")),
) -> Product:
    exists = session.exec(
        select(Product).where(Product.tenant_id == admin.tenant_id, Product.sku == payload.sku)
    ).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sku already exists")

    check_limit(session, admin.tenant_id, "MAX_SKUS")

    product = Product(tenant_id=admin.tenant_id, **payload.model_dump())
    session.add(product)
    session.commit()
    session.refresh(product)

    increment_usage(session, admin.tenant_id, "MAX_SKUS")
    return product


@router.get("")
async def list_products(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    _feature: None = Depends(require_feature("PRODUCT_MASTER")),
) -> list[ProductRead | ProductReadPublic]:
    products = session.exec(tenant_scoped(Product, user.tenant_id)).all()
    return [_serialize(p, user) for p in products]


@router.get("/{product_id}")
async def get_product(
    product_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    _feature: None = Depends(require_feature("PRODUCT_MASTER")),
) -> ProductRead | ProductReadPublic:
    product = get_tenant_owned(session, Product, product_id, user.tenant_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    return _serialize(product, user)


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("PRODUCT_MASTER")),
) -> Product:
    product = get_tenant_owned(session, Product, product_id, admin.tenant_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    product.updated_at = datetime.now(timezone.utc)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_product(
    product_id: uuid.UUID,
    session: Session = Depends(get_session),
    admin: User = Depends(require_role(UserRole.admin)),
    _feature: None = Depends(require_feature("PRODUCT_MASTER")),
) -> None:
    product = get_tenant_owned(session, Product, product_id, admin.tenant_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    product.is_active = False
    product.updated_at = datetime.now(timezone.utc)
    session.add(product)
    session.commit()
