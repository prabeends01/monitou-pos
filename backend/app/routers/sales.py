import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.db import get_session
from app.models.sale import Sale, SaleItem
from app.models.user import User, UserRole
from app.schemas.sale import SaleCreate, SaleRead
from app.services.invoicing import render_invoice_pdf
from app.services.sales import create_sale

router = APIRouter(prefix="/sales", tags=["sales"])


def _to_read(session: Session, sale: Sale) -> SaleRead:
    items = session.exec(select(SaleItem).where(SaleItem.sale_id == sale.id)).all()
    return SaleRead.model_validate(
        {**sale.model_dump(), "items": [item.model_dump() for item in items]}
    )


@router.post("", response_model=SaleRead, status_code=status.HTTP_201_CREATED)
async def post_sale(
    payload: SaleCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> SaleRead:
    sale = create_sale(session, payload, cashier_id=user.id)
    return _to_read(session, sale)


@router.get("/{sale_id}", response_model=SaleRead)
async def get_sale(
    sale_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> SaleRead:
    sale = session.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sale not found")
    if user.role != UserRole.admin and sale.cashier_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your sale")
    return _to_read(session, sale)


@router.get("", response_model=list[SaleRead])
async def list_sales(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[SaleRead]:
    query = select(Sale)
    if user.role != UserRole.admin:
        query = query.where(Sale.cashier_id == user.id)
    sales = session.exec(query).all()
    return [_to_read(session, sale) for sale in sales]


@router.get("/{sale_id}/invoice")
async def get_sale_invoice(
    sale_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Response:
    sale = session.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sale not found")
    if user.role != UserRole.admin and sale.cashier_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your sale")
    pdf_bytes = render_invoice_pdf(session, sale)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{sale.invoice_number}.pdf"'},
    )
