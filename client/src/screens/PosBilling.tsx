import {
  Body1Strong,
  Body1,
  Button,
  Caption1,
  Dropdown,
  Input,
  Option,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Title2,
  Toast,
  ToastTitle,
  Toaster,
  makeStyles,
  tokens,
  useId,
  useToastController,
} from "@fluentui/react-components";
import { invoke } from "@tauri-apps/api/core";
import { useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { toSalePayload } from "../cart";
import { config } from "../config";
import { useAppServices } from "../AppContext";
import { useCartStore } from "../stores/cartStore";
import type { BarcodeScanResult } from "../types";

const PAYMENT_MODES = ["cash", "card", "upi"];
const SEARCH_DEBOUNCE_MS = 250;

const useSearchStyles = makeStyles({
  root: {
    position: "relative",
    width: "420px",
  },
  dropdown: {
    position: "absolute",
    top: "calc(100% + 4px)",
    left: 0,
    right: 0,
    zIndex: 10,
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    boxShadow: tokens.shadow16,
    maxHeight: "320px",
    overflowY: "auto",
  },
  row: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "12px",
    padding: "8px 12px",
    cursor: "pointer",
  },
  rowActive: {
    backgroundColor: tokens.colorNeutralBackground1Selected,
  },
});

/** Editable qty cell. Keeps its own draft text separate from the committed
 * store value so backspacing to empty (to retype a number) doesn't get
 * immediately snapped back to 1 by the store's min-1 clamp — the clamp only
 * applies once there's a valid positive number to commit, or on blur if the
 * field was left empty/invalid. Typing 0 (or a negative) is never accepted
 * as a real quantity — it snaps straight to 1 instead of sitting in the
 * field showing a qty the line total doesn't match; removing a line is what
 * the Remove button is for. */
function QtyInput({ value, onChange }: { value: number; onChange: (qty: number) => void }) {
  const [text, setText] = useState(String(value));

  useEffect(() => {
    setText(String(value));
  }, [value]);

  return (
    <Input
      type="number"
      min={1}
      value={text}
      onChange={(_, data) => {
        if (data.value === "") {
          setText("");
          return;
        }
        const parsed = Number(data.value);
        if (!Number.isFinite(parsed)) return;
        if (parsed <= 0) {
          setText("1");
          onChange(1);
          return;
        }
        setText(data.value);
        onChange(Math.floor(parsed));
      }}
      onBlur={() => {
        const parsed = Number(text);
        if (!text || !Number.isFinite(parsed) || parsed <= 0) setText(String(value));
      }}
      style={{ width: 90 }}
    />
  );
}

/** Search-as-you-type over barcode value, SKU, and product name, straight
 * against the server (debounced — every keystroke is now a network call,
 * not an instant local query). A scanner's rapid barcode+Enter still
 * resolves via the exact-match fallback even if the debounced search
 * hasn't caught up yet. */
function ProductSearch({ onSelect }: { onSelect: (row: BarcodeScanResult) => void }) {
  const styles = useSearchStyles();
  const { api } = useAppServices();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<BarcodeScanResult[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setOpen(false);
      setLoading(false);
      return;
    }
    setLoading(true);
    const timer = setTimeout(() => {
      api
        .searchProducts(trimmed)
        .then((rows) => {
          setResults(rows);
          setActiveIndex(0);
          setOpen(rows.length > 0);
        })
        .catch((err) => console.error("product search failed", err))
        .finally(() => setLoading(false));
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query, api]);

  function select(row: BarcodeScanResult) {
    onSelect(row);
    setQuery("");
    setResults([]);
    setOpen(false);
    setError(null);
    inputRef.current?.focus();
  }

  async function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
      return;
    }
    if (e.key === "Escape") {
      setOpen(false);
      return;
    }
    if (e.key !== "Enter") return;
    e.preventDefault();

    const value = query.trim();
    if (!value) return;

    if (open && results[activeIndex]) {
      select(results[activeIndex]);
      return;
    }
    // scanner-gun fallback: exact barcode match against the server, no
    // dependency on the debounced search having caught up yet
    try {
      const row = await api.getBarcode(value);
      select(row);
    } catch (err) {
      setError(err instanceof ApiError ? `No product found for "${value}"` : "Cannot reach server");
    }
  }

  return (
    <div className={styles.root}>
      <Input
        ref={inputRef}
        placeholder="Scan barcode, or type SKU / product name…"
        value={query}
        onChange={(_, data) => {
          setQuery(data.value);
          setError(null);
        }}
        onKeyDown={handleKeyDown}
        contentAfter={loading ? <Spinner size="tiny" /> : undefined}
        autoFocus
        style={{ width: "100%" }}
      />
      {error && <Body1Strong style={{ color: tokens.colorPaletteRedForeground1 }}>{error}</Body1Strong>}
      {open && (
        <div className={styles.dropdown}>
          {results.map((row, i) => (
            <div
              key={row.barcode.id}
              className={`${styles.row} ${i === activeIndex ? styles.rowActive : ""}`}
              onMouseEnter={() => setActiveIndex(i)}
              onMouseDown={(e) => e.preventDefault()} // keep input focus through the click
              onClick={() => select(row)}
            >
              <div>
                <Body1>{row.product_name}</Body1>
                <div>
                  <Caption1>
                    {row.product_sku} · {row.barcode.label} · {row.barcode.barcode_value}
                  </Caption1>
                </div>
              </div>
              <Caption1>₹{row.sale_price}</Caption1>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PosBilling() {
  const { api } = useAppServices();
  const lines = useCartStore((s) => s.lines);
  const addScan = useCartStore((s) => s.addScan);
  const setQty = useCartStore((s) => s.setQty);
  const removeLine = useCartStore((s) => s.removeLine);
  const clear = useCartStore((s) => s.clear);
  const subtotal = useCartStore((s) => s.subtotal);

  const [paymentMode, setPaymentMode] = useState(PAYMENT_MODES[0]);
  const [checkingOut, setCheckingOut] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  const toasterId = useId("pos-toaster");
  const { dispatchToast } = useToastController(toasterId);

  async function handleCheckout() {
    if (lines.length === 0) return;
    setCheckingOut(true);
    setCheckoutError(null);

    const payload = toSalePayload(lines, {
      invoiceSeries: config.invoiceSeries,
      terminalId: config.terminalId,
      paymentMode,
      // GST rate handling is an open decision — CLAUDE.md Section 9
      gstAmount: "0",
    });

    let sale;
    try {
      sale = await api.createSale(payload);
    } catch (err) {
      // Cart is intentionally left intact — no local queue anymore, so a
      // failed checkout must be visibly retryable, not silently lost.
      setCheckoutError(err instanceof ApiError ? err.detail : "Could not reach the server — try again");
      setCheckingOut(false);
      return;
    }

    if (config.printerHost) {
      try {
        await invoke("print_receipt", {
          host: config.printerHost,
          port: config.printerPort,
          receipt: {
            invoice_number: sale.invoice_number,
            created_at_client: sale.created_at_client,
            payment_mode: sale.payment_mode,
            gst_amount: sale.gst_amount,
            total_amount: sale.total_amount,
            items: lines.map((l) => ({ name: l.name, qty_base_units: l.qtyBaseUnits, unit_price: l.unitPrice })),
          },
        });
      } catch (err) {
        console.error("receipt print failed", err);
      }
    }

    dispatchToast(
      <Toast>
        <ToastTitle>Sale recorded — invoice {sale.invoice_number}</ToastTitle>
      </Toast>,
      { intent: "success" },
    );
    clear();
    setCheckingOut(false);
  }

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <Toaster toasterId={toasterId} />
      <Title2>POS Billing</Title2>
      <ProductSearch onSelect={addScan} />

      <Table aria-label="Cart">
        <TableHeader>
          <TableRow>
            <TableHeaderCell>SKU</TableHeaderCell>
            <TableHeaderCell>Name</TableHeaderCell>
            <TableHeaderCell>Qty</TableHeaderCell>
            <TableHeaderCell>Unit price</TableHeaderCell>
            <TableHeaderCell>Line total</TableHeaderCell>
            <TableHeaderCell></TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {lines.map((line) => (
            <TableRow key={line.barcodeId}>
              <TableCell>{line.sku}</TableCell>
              <TableCell>{line.name}</TableCell>
              <TableCell>
                <QtyInput value={line.qtyBaseUnits} onChange={(qty) => setQty(line.barcodeId, qty)} />
              </TableCell>
              <TableCell>{Number(line.unitPrice).toFixed(2)}</TableCell>
              <TableCell>{(Number(line.unitPrice) * line.qtyBaseUnits).toFixed(2)}</TableCell>
              <TableCell>
                <Button size="small" onClick={() => removeLine(line.barcodeId)}>
                  Remove
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Body1Strong>Total: {subtotal().toFixed(2)}</Body1Strong>
      {checkoutError && (
        <Body1Strong style={{ color: tokens.colorPaletteRedForeground1 }}>{checkoutError}</Body1Strong>
      )}

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <Dropdown
          value={paymentMode}
          selectedOptions={[paymentMode]}
          onOptionSelect={(_, data) => setPaymentMode(data.optionValue ?? PAYMENT_MODES[0])}
        >
          {PAYMENT_MODES.map((mode) => (
            <Option key={mode} value={mode}>
              {mode}
            </Option>
          ))}
        </Dropdown>
        <Button appearance="primary" onClick={handleCheckout} disabled={lines.length === 0 || checkingOut}>
          {checkingOut ? "Processing…" : "Checkout"}
        </Button>
        <Button onClick={clear} disabled={lines.length === 0 || checkingOut}>
          Clear cart
        </Button>
      </div>
    </div>
  );
}
