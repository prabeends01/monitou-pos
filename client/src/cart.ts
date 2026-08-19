import type { BarcodeScanResult, SaleCreatePayload } from "./types";

export interface CartLine {
  barcodeId: string;
  productId: string;
  sku: string;
  name: string;
  /** Final quantity in base units — editable, not "number of scans". A box
   * scan defaults to its pack_qty (e.g. 100) but the cashier can edit it
   * down for a partial sale from an opened box. */
  qtyBaseUnits: number;
  unitPrice: string; // price per base unit, decimal string to avoid float drift
}

export function lineTotal(line: CartLine): number {
  return Number(line.unitPrice) * line.qtyBaseUnits;
}

/** Adds a scanned/searched barcode to the cart. A new line defaults to the
 * barcode's pack_qty (a box-of-100 barcode starts the line at 100, editable
 * from there); scanning the same barcode again adds another pack_qty's
 * worth. */
export function addScan(lines: CartLine[], row: BarcodeScanResult): CartLine[] {
  const barcodeId = row.barcode.id;
  const existing = lines.find((l) => l.barcodeId === barcodeId);
  if (existing) {
    return lines.map((l) =>
      l.barcodeId === barcodeId ? { ...l, qtyBaseUnits: l.qtyBaseUnits + row.barcode.pack_qty } : l,
    );
  }
  return [
    ...lines,
    {
      barcodeId,
      productId: row.product_id,
      sku: row.product_sku,
      name: row.product_name,
      qtyBaseUnits: row.barcode.pack_qty,
      unitPrice: row.sale_price,
    },
  ];
}

/** Directly overwrites a line's quantity — used by the editable qty field
 * in POS billing. Clamped to at least 1; use removeLine to drop a line. */
export function setQty(lines: CartLine[], barcodeId: string, qtyBaseUnits: number): CartLine[] {
  const clamped = Math.max(1, Math.floor(qtyBaseUnits) || 1);
  return lines.map((l) => (l.barcodeId === barcodeId ? { ...l, qtyBaseUnits: clamped } : l));
}

export function removeLine(lines: CartLine[], barcodeId: string): CartLine[] {
  return lines.filter((l) => l.barcodeId !== barcodeId);
}

export function subtotal(lines: CartLine[]): number {
  return lines.reduce((sum, l) => sum + lineTotal(l), 0);
}

export interface SalePayloadOptions {
  invoiceSeries: string;
  terminalId: string;
  paymentMode: string;
  gstAmount: string;
  customerId?: string | null;
}

/** `invoice_number` is omitted — the server assigns it (see SaleCreatePayload). */
export function toSalePayload(lines: CartLine[], opts: SalePayloadOptions): SaleCreatePayload {
  return {
    id: crypto.randomUUID(),
    invoice_series: opts.invoiceSeries,
    terminal_id: opts.terminalId,
    customer_id: opts.customerId ?? null,
    payment_mode: opts.paymentMode,
    gst_amount: opts.gstAmount,
    created_at_client: new Date().toISOString(),
    items: lines.map((line) => ({
      id: crypto.randomUUID(),
      product_id: line.productId,
      barcode_id: line.barcodeId,
      qty_base_units: line.qtyBaseUnits,
      unit_price: line.unitPrice,
    })),
  };
}
