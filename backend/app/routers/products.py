import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_role
from app.db import get_session
from app.models.product import Product
from app.models.user import User, UserRole
from app.schemas.product import ProductCreate, ProductRead, ProductReadPublic, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


def _serialize(product: Product, user: User) -> ProductRead | ProductReadPublic:
    model = ProductRead if user.role == UserRole.admin else ProductReadPublic
    return model.model_validate(product, from_attributes=True)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role(UserRole.admin)),
) -> Product:
    if session.exec(select(Product).where(Product.sku == payload.sku)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="sku already exists")
    product = Product.model_validate(payload)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.get("")
async def list_products(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ProductRead | ProductReadPublic]:
    products = session.exec(select(Product)).all()
    return [_serialize(p, user) for p in products]


@router.get("/{product_id}")
async def get_product(
    product_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ProductRead | ProductReadPublic:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    return _serialize(product, user)


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_role(UserRole.admin)),
) -> Product:
    product = session.get(Product, product_id)
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
    _admin: User = Depends(require_role(UserRole.admin)),
) -> None:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    product.is_active = False
    product.updated_at = datetime.now(timezone.utc)
    session.add(product)
    session.commit()
