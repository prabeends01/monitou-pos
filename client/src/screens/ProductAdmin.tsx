import {
  Body1Strong,
  Button,
  Field,
  Input,
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

/** Admin-only product catalog management. The server still enforces
 * admin-only writes independently (require_role) — this screen just keeps
 * a sales-role user from seeing controls they can't use. */
export default function ProductAdmin() {
  const { api } = useAppServices();
  const queryClient = useQueryClient();

  const productsQuery = useQuery({ queryKey: ["products"], queryFn: () => api.getProducts() });

  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [costPrice, setCostPrice] = useState("");
  const [salePrice, setSalePrice] = useState("");
  const [reorderThreshold, setReorderThreshold] = useState("0");
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      api.createProduct({
        sku,
        name,
        category,
        cost_price: costPrice,
        sale_price: salePrice,
        reorder_threshold: Number(reorderThreshold) || 0,
      }),
    onSuccess: () => {
      setSku("");
      setName("");
      setCategory("");
      setCostPrice("");
      setSalePrice("");
      setReorderThreshold("0");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.detail : String(err)),
  });

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <Title2>Products</Title2>

      <Table aria-label="Products">
        <TableHeader>
          <TableRow>
            <TableHeaderCell>SKU</TableHeaderCell>
            <TableHeaderCell>Name</TableHeaderCell>
            <TableHeaderCell>Category</TableHeaderCell>
            <TableHeaderCell>Cost</TableHeaderCell>
            <TableHeaderCell>Sale price</TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(productsQuery.data ?? []).map((product) => (
            <TableRow key={product.id}>
              <TableCell>{product.sku}</TableCell>
              <TableCell>{product.name}</TableCell>
              <TableCell>{product.category}</TableCell>
              <TableCell>{product.cost_price ?? ""}</TableCell>
              <TableCell>{product.sale_price}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Body1Strong>Create product</Body1Strong>
      {error && <span style={{ color: "var(--colorPaletteRedForeground1)" }}>{error}</span>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Field label="SKU">
          <Input value={sku} onChange={(_, d) => setSku(d.value)} />
        </Field>
        <Field label="Name">
          <Input value={name} onChange={(_, d) => setName(d.value)} />
        </Field>
        <Field label="Category">
          <Input value={category} onChange={(_, d) => setCategory(d.value)} />
        </Field>
        <Field label="Cost price">
          <Input value={costPrice} onChange={(_, d) => setCostPrice(d.value)} />
        </Field>
        <Field label="Sale price">
          <Input value={salePrice} onChange={(_, d) => setSalePrice(d.value)} />
        </Field>
        <Field label="Reorder threshold">
          <Input value={reorderThreshold} onChange={(_, d) => setReorderThreshold(d.value)} />
        </Field>
      </div>
      <Button
        appearance="primary"
        onClick={() => createMutation.mutate()}
        disabled={!sku || !name || createMutation.isPending}
      >
        Create product
      </Button>
    </div>
  );
}
