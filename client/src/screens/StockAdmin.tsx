import {
  Body1Strong,
  Button,
  Dropdown,
  Field,
  Input,
  Option,
  Title2,
} from "@fluentui/react-components";
import { useState } from "react";

import { ApiError } from "../api/client";
import { useAppServices } from "../AppContext";
import { config } from "../config";

const MOVEMENT_KINDS = ["Purchase receive", "Adjustment"] as const;

/** Admin-only stock adjustments and purchase receiving. */
export default function StockAdmin() {
  const { api } = useAppServices();
  const [productId, setProductId] = useState("");
  const [qty, setQty] = useState("0");
  const [kind, setKind] = useState<(typeof MOVEMENT_KINDS)[number]>("Purchase receive");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [balance, setBalance] = useState<number | null>(null);

  async function handleSubmit() {
    if (!productId) {
      setError("Enter a product ID");
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
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12, maxWidth: 400 }}>
      <Title2>Stock adjustments / purchase receiving</Title2>
      <Field label="Product ID">
        <Input value={productId} onChange={(_, d) => setProductId(d.value)} placeholder="product UUID" />
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
