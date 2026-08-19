from sqlmodel import Session, select

from app.models.customer import Customer
from app.models.product import Product
from app.models.sale import Sale, SaleItem

_INVOICE_TEMPLATE = """
<html>
<head>
<style>
  body {{ font-family: sans-serif; font-size: 12px; }}
  h1 {{ font-size: 18px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
  th, td {{ border: 1px solid #999; padding: 4px 8px; text-align: left; }}
  .totals td {{ border: none; text-align: right; }}
</style>
</head>
<body>
  <h1>Monitou Spare Parts — Tax Invoice</h1>
  <p>Invoice No: <b>{invoice_number}</b> ({invoice_series})<br/>
     Date: {created_at_client}<br/>
     Customer: {customer_name}<br/>
     Payment mode: {payment_mode}</p>
  <table>
    <tr><th>SKU</th><th>Product</th><th>Qty (base units)</th><th>Unit price</th><th>Line total</th></tr>
    {rows}
  </table>
  <table class="totals">
    <tr><td>GST</td><td>{gst_amount}</td></tr>
    <tr><td><b>Total</b></td><td><b>{total_amount}</b></td></tr>
  </table>
</body>
</html>
"""


def render_invoice_html(session: Session, sale: Sale) -> str:
    items = session.exec(select(SaleItem).where(SaleItem.sale_id == sale.id)).all()
    rows = []
    for item in items:
        product = session.get(Product, item.product_id)
        line_total = item.unit_price * item.qty_base_units
        rows.append(
            f"<tr><td>{product.sku if product else ''}</td>"
            f"<td>{product.name if product else ''}</td>"
            f"<td>{item.qty_base_units}</td>"
            f"<td>{item.unit_price}</td>"
            f"<td>{line_total}</td></tr>"
        )

    customer_name = "Walk-in"
    if sale.customer_id is not None:
        customer = session.get(Customer, sale.customer_id)
        if customer is not None:
            customer_name = customer.name

    return _INVOICE_TEMPLATE.format(
        invoice_number=sale.invoice_number,
        invoice_series=sale.invoice_series,
        created_at_client=sale.created_at_client,
        customer_name=customer_name,
        payment_mode=sale.payment_mode,
        rows="".join(rows),
        gst_amount=sale.gst_amount,
        total_amount=sale.total_amount,
    )


def render_invoice_pdf(session: Session, sale: Sale) -> bytes:
    from weasyprint import HTML  # imported lazily: heavy native dependency, only needed for PDF export

    html = render_invoice_html(session, sale)
    return HTML(string=html).write_pdf()
