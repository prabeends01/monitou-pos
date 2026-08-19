import { describe, expect, it } from "vitest";

import { addScan, lineTotal, removeLine, setQty, subtotal, toSalePayload } from "./cart";
import type { BarcodeScanResult } from "./types";

function barcodeRow(overrides: Partial<BarcodeScanResult> = {}): BarcodeScanResult {
  return {
    barcode: {
      id: "b1",
      product_id: "p1",
      barcode_value: "8900000000011",
      pack_qty: 1,
      label: "Single piece",
      updated_at: "2026-01-01T00:00:00Z",
    },
    product_id: "p1",
    product_sku: "SKU-1",
    product_name: "Widget",
    base_units_per_scan: 1,
    sale_price: "5.00",
    ...overrides,
  };
}

function withBarcode(overrides: Partial<BarcodeScanResult["barcode"]>, rest: Partial<BarcodeScanResult> = {}) {
  const base = barcodeRow(rest);
  return { ...base, barcode: { ...base.barcode, ...overrides } };
}

describe("cart", () => {
  it("addScan creates a new line defaulting qty to the barcode's pack_qty", () => {
    const lines = addScan([], barcodeRow());
    expect(lines).toHaveLength(1);
    expect(lines[0].qtyBaseUnits).toBe(1);
    expect(subtotal(lines)).toBe(5);
  });

  it("scanning a box barcode defaults qty to the full pack, not 1", () => {
    const lines = addScan([], withBarcode({ pack_qty: 100 }));
    expect(lines[0].qtyBaseUnits).toBe(100);
    expect(subtotal(lines)).toBe(500);
  });

  it("scanning the same barcode twice adds another pack_qty, not a new line", () => {
    let lines = addScan([], withBarcode({ pack_qty: 100 }));
    lines = addScan(lines, withBarcode({ pack_qty: 100 }));
    expect(lines).toHaveLength(1);
    expect(lines[0].qtyBaseUnits).toBe(200);
  });

  it("setQty overwrites the line's quantity directly — partial sale from an opened box", () => {
    let lines = addScan([], withBarcode({ pack_qty: 100 }));
    expect(lines[0].qtyBaseUnits).toBe(100);
    lines = setQty(lines, "b1", 25);
    expect(lines[0].qtyBaseUnits).toBe(25);
    expect(subtotal(lines)).toBe(125);
  });

  it("setQty clamps below 1 up to 1", () => {
    let lines = addScan([], barcodeRow());
    lines = setQty(lines, "b1", 0);
    expect(lines[0].qtyBaseUnits).toBe(1);
  });

  it("removeLine drops only the matching line", () => {
    let lines = addScan([], withBarcode({ id: "b1" }));
    lines = addScan(lines, withBarcode({ id: "b2" }, { product_id: "p2" }));
    lines = removeLine(lines, "b1");
    expect(lines).toHaveLength(1);
    expect(lines[0].barcodeId).toBe("b2");
  });

  it("lineTotal multiplies unit price by qty", () => {
    let lines = addScan([], barcodeRow({ sale_price: "5.00" }));
    lines = setQty(lines, "b1", 2);
    expect(lineTotal(lines[0])).toBe(10);
  });

  it("toSalePayload shapes items with product/barcode ids and qty_base_units, omits invoice_number", () => {
    const lines = addScan([], withBarcode({ pack_qty: 100 }));
    const payload = toSalePayload(lines, {
      invoiceSeries: "T1",
      terminalId: "T1",
      paymentMode: "cash",
      gstAmount: "18.00",
    });
    expect(payload.invoice_number).toBeUndefined();
    expect(payload.items).toHaveLength(1);
    expect(payload.items[0].qty_base_units).toBe(100);
    expect(payload.items[0].product_id).toBe("p1");
    expect(payload.items[0].barcode_id).toBe("b1");
  });

  it("toSalePayload reflects an edited partial quantity", () => {
    let lines = addScan([], withBarcode({ pack_qty: 100 }));
    lines = setQty(lines, "b1", 25);
    const payload = toSalePayload(lines, {
      invoiceSeries: "T1",
      terminalId: "T1",
      paymentMode: "cash",
      gstAmount: "0",
    });
    expect(payload.items[0].qty_base_units).toBe(25);
  });
});
