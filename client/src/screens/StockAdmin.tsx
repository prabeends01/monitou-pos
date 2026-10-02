import {
  Badge,
  Body1Strong,
  Button,
  Combobox,
  Dropdown,
  Field,
  Input,
  Option,
  Spinner,
  Tab,
  TabList,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Title2,
  type SelectTabData,
} from "@fluentui/react-components";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { useAppServices } from "../AppContext";
import { config } from "../config";
import type { CurrentStockRow } from "../types";

const MOVEMENT_KINDS = ["Purchase receive", "Adjustment"] as const;

function stockStatus(row: CurrentStockRow): { label: string; color: "danger" | "warning" | "success" } {
  if (row.on_hand_qty <= 0) return { label: "Out of stock", color: "danger" };
  if (row.on_hand_qty <= row.reorder_threshold) return { label: "Low stock", color: "warning" };
  return { label: "In stock", color: "success" };
}

function CurrentStockView() {
  const { api } = useAppServices();
  const [search, setSearch] = useState("");
  const stockQuery = useQuery({
    queryKey: ["current-stock"],
    queryFn: () => api.getCurrentStock(),
    enabled: false,
  });

  const rows = stockQuery.data ?? [];
  const filtered = useMemo(
    () =>
      rows.filter(
        (r) =>
          `${r.sku} ${r.name} ${r.category} ${r.oem_part_number || ""}`.toLowerCase().includes(search.toLowerCase()),
      ),
    [rows, search],
  );
  const outOfStock = rows.filter((r) => r.on_hand_qty <= 0).length;
  const lowStock = rows.filter((r) => r.on_hand_qty > 0 && r.on_hand_qty <= r.reorder_threshold).length;

  async function handleDownload() {
    try {
      await api.downloadStockCSV();
    } catch (err) {
      console.error("CSV download failed", err);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
        <Button appearance="primary" onClick={() => stockQuery.refetch()} disabled={stockQuery.isFetching}>
          {stockQuery.isFetching ? <Spinner size="tiny" /> : "Generate current stock"}
        </Button>
        {rows.length > 0 && (
          <Button onClick={handleDownload} disabled={stockQuery.isFetching}>
            Download CSV
          </Button>
        )}
        {rows.length > 0 && (
          <Field label="Search" style={{ minWidth: 220 }}>
            <Input
              value={search}
              onChange={(_, d) => setSearch(d.value)}
              placeholder="Filter by SKU, name, or category"
            />
          </Field>
        )}
        {rows.length > 0 && (
          <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
            <Badge appearance="tint" color="informative">
              {rows.length} SKUs
            </Badge>
            <Badge appearance="tint" color="warning">
              {lowStock} low
            </Badge>
            <Badge appearance="tint" color="danger">
              {outOfStock} out
            </Badge>
          </div>
        )}
      </div>

      {stockQuery.error && (
        <span style={{ color: "var(--colorPaletteRedForeground1)" }}>
          {stockQuery.error instanceof ApiError ? stockQuery.error.detail : String(stockQuery.error)}
        </span>
      )}

      {!stockQuery.isFetching && rows.length === 0 && !stockQuery.error && (
        <Body1Strong>Click "Generate current stock" to load the latest balances.</Body1Strong>
      )}

      {rows.length > 0 && (
        <div
          style={{
            maxHeight: "60vh",
            overflowY: "auto",
            border: "1px solid var(--colorNeutralStroke2)",
            borderRadius: 8,
          }}
        >
          <Table size="small" style={{ minWidth: 1100 }}>
            <TableHeader
              style={{ position: "sticky", top: 0, background: "var(--colorNeutralBackground1)", zIndex: 1 }}
            >
              <TableRow>
                <TableHeaderCell>SKU</TableHeaderCell>
                <TableHeaderCell>Name</TableHeaderCell>
                <TableHeaderCell>OEM Part #</TableHeaderCell>
                <TableHeaderCell>Category</TableHeaderCell>
                <TableHeaderCell>Brand</TableHeaderCell>
                <TableHeaderCell>Location</TableHeaderCell>
                <TableHeaderCell>On Hand</TableHeaderCell>
                <TableHeaderCell>Reserved</TableHeaderCell>
                <TableHeaderCell>Available</TableHeaderCell>
                <TableHeaderCell>On Order</TableHeaderCell>
                <TableHeaderCell>Reorder At</TableHeaderCell>
                <TableHeaderCell>Supplier</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((row) => {
                const status = stockStatus(row);
                const location = [row.warehouse, row.rack, row.bin_location].filter(Boolean).join("/") || "-";
                return (
                  <TableRow key={row.product_id}>
                    <TableCell>{row.sku}</TableCell>
                    <TableCell>{row.name}</TableCell>
                    <TableCell>{row.oem_part_number || "-"}</TableCell>
                    <TableCell>{row.category}</TableCell>
                    <TableCell>{row.brand || "-"}</TableCell>
                    <TableCell>{location}</TableCell>
                    <TableCell>
                      <Body1Strong>{row.on_hand_qty}</Body1Strong>
                    </TableCell>
                    <TableCell>{row.reserved_qty}</TableCell>
                    <TableCell>{row.available_qty}</TableCell>
                    <TableCell>{row.on_order_qty}</TableCell>
                    <TableCell>{row.reorder_threshold}</TableCell>
                    <TableCell>{row.supplier_name || "-"}</TableCell>
                    <TableCell>
                      <Badge appearance="tint" color={status.color}>
                        {status.label}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          {filtered.length === 0 && (
            <div style={{ padding: 12 }}>
              <Body1Strong>No product matches "{search}".</Body1Strong>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AdjustmentsView() {
  const { api } = useAppServices();
  const productsQuery = useQuery({ queryKey: ["products"], queryFn: () => api.getProducts() });
  const products = productsQuery.data ?? [];
  const [productId, setProductId] = useState("");
  const [productQuery, setProductQuery] = useState("");
  const [qty, setQty] = useState("0");
  const [kind, setKind] = useState<(typeof MOVEMENT_KINDS)[number]>("Purchase receive");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [balance, setBalance] = useState<number | null>(null);

  async function handleSubmit() {
    if (!productId) {
      setError("Select a product");
      return;
    }
    setError(null);
    setMessage(null);
    const payload = {
      id: crypto.randomUUID(),
      product_id: productId,
      qty_base_units: Number(qty) || 0,
      terminal_id: config.terminalId,
    };
    try {
      const result =
        kind === "Purchase receive" ? await api.purchaseReceive(payload) : await api.stockAdjustment(payload);
      let msg = `Balance after: ${result.balance_after}`;
      if (result.went_negative) msg += " — WARNING: balance is negative, flag for review.";
      setMessage(msg);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  async function handleCheckBalance() {
    if (!productId) return;
    try {
      const result = await api.stockBalance(productId);
      setBalance(result.balance);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 400 }}>
      <Field label="Product">
        <Combobox
          freeform
          autoComplete="off"
          value={productQuery}
          selectedOptions={productId ? [productId] : []}
          onChange={(e) => {
            setProductQuery(e.target.value);
            setProductId("");
          }}
          onOptionSelect={(_, data) => {
            setProductId(data.optionValue ?? "");
            setProductQuery(data.optionText ?? "");
          }}
        >
          {products
            .filter((p) => `${p.sku} ${p.name}`.toLowerCase().includes(productQuery.toLowerCase()))
            .map((p) => (
              <Option key={p.id} value={p.id} text={`${p.sku} — ${p.name}`}>
                {p.sku} — {p.name}
              </Option>
            ))}
        </Combobox>
      </Field>
      <Field label="Movement">
        <Dropdown
          value={kind}
          selectedOptions={[kind]}
          onOptionSelect={(_, d) => setKind((d.optionValue as (typeof MOVEMENT_KINDS)[number]) ?? kind)}
        >
          {MOVEMENT_KINDS.map((k) => (
            <Option key={k} value={k}>
              {k}
            </Option>
          ))}
        </Dropdown>
      </Field>
      <Field label="Qty (base units)">
        <Input value={qty} onChange={(_, d) => setQty(d.value)} type="number" />
      </Field>
      <div style={{ display: "flex", gap: 8 }}>
        <Button appearance="primary" onClick={handleSubmit}>
          Submit
        </Button>
        <Button onClick={handleCheckBalance}>Check balance</Button>
      </div>
      {error && <span style={{ color: "var(--colorPaletteRedForeground1)" }}>{error}</span>}
      {message && <Body1Strong>{message}</Body1Strong>}
      {balance !== null && <Body1Strong>Current balance: {balance}</Body1Strong>}
    </div>
  );
}

/** Admin-only stock: current-stock overview plus adjustments / purchase receiving. */
export default function StockAdmin() {
  const [tab, setTab] = useState<"current" | "adjust">("current");

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
      <Title2>Stock</Title2>
      <TabList
        selectedValue={tab}
        onTabSelect={(_, data: SelectTabData) => setTab(data.value as "current" | "adjust")}
      >
        <Tab value="current">Current stock</Tab>
        <Tab value="adjust">Stock adjustments / purchase receiving</Tab>
      </TabList>
      {tab === "current" ? <CurrentStockView /> : <AdjustmentsView />}
    </div>
  );
}
