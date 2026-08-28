import {
  Body1Strong,
  Button,
  Dropdown,
  Field,
  Input,
  Option,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Title2,
} from "@fluentui/react-components";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "../api/client";
import { useAppServices } from "../AppContext";
import type { Barcode } from "../types";

/** Admin-only barcode/pack-size management — Essential+ (BARCODE_GENERATION,
 * enforced server-side; see routers/barcodes.py and CLAUDE.md Stage 5). No
 * `GET /barcodes` list-all endpoint exists yet, so this only shows barcodes
 * created in the current session rather than the tenant's full history —
 * a real "all barcodes for this product" list is a separate backend
 * addition, not part of Stage 8's navigation work. */
export default function BarcodeAdmin() {
  const { api } = useAppServices();
  const queryClient = useQueryClient();

  const productsQuery = useQuery({ queryKey: ["products"], queryFn: () => api.getProducts() });

  const [productId, setProductId] = useState("");
  const [barcodeValue, setBarcodeValue] = useState("");
  const [packQty, setPackQty] = useState("1");
  const [label, setLabel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Barcode[]>([]);

  const createMutation = useMutation({
    mutationFn: () =>
      api.createBarcode({
        product_id: productId,
        barcode_value: barcodeValue,
        pack_qty: Number(packQty) || 1,
        label,
      }),
    onSuccess: (barcode) => {
      setCreated((prev) => [barcode, ...prev]);
      setBarcodeValue("");
      setPackQty("1");
      setLabel("");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.detail : String(err)),
  });

  const products = productsQuery.data ?? [];
  const selectedProduct = products.find((p) => p.id === productId);

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <Title2>Barcodes</Title2>

      <Body1Strong>Add a barcode</Body1Strong>
      {error && <span style={{ color: "var(--colorPaletteRedForeground1)" }}>{error}</span>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
        <Field label="Product">
          <Dropdown
            value={selectedProduct ? `${selectedProduct.sku} — ${selectedProduct.name}` : ""}
            selectedOptions={productId ? [productId] : []}
            onOptionSelect={(_, data) => setProductId(data.optionValue ?? "")}
          >
            {products.map((p) => (
              <Option key={p.id} value={p.id} text={`${p.sku} — ${p.name}`}>
                {p.sku} — {p.name}
              </Option>
            ))}
          </Dropdown>
        </Field>
        <Field label="Barcode value">
          <Input value={barcodeValue} onChange={(_, d) => setBarcodeValue(d.value)} />
        </Field>
        <Field label="Pack qty">
          <Input value={packQty} onChange={(_, d) => setPackQty(d.value)} />
        </Field>
        <Field label="Label">
          <Input value={label} onChange={(_, d) => setLabel(d.value)} placeholder="e.g. Box of 100" />
        </Field>
        <Button
          appearance="primary"
          onClick={() => createMutation.mutate()}
          disabled={!productId || !barcodeValue || !label || createMutation.isPending}
        >
          Add barcode
        </Button>
      </div>

      {created.length > 0 && (
        <>
          <Body1Strong>Added this session</Body1Strong>
          <Table aria-label="Newly created barcodes">
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Barcode value</TableHeaderCell>
                <TableHeaderCell>Pack qty</TableHeaderCell>
                <TableHeaderCell>Label</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {created.map((b) => (
                <TableRow key={b.id}>
                  <TableCell>{b.barcode_value}</TableCell>
                  <TableCell>{b.pack_qty}</TableCell>
                  <TableCell>{b.label}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </div>
  );
}
