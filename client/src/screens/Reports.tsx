import {
  Button,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Title2,
} from "@fluentui/react-components";
import { useQuery } from "@tanstack/react-query";
import { save } from "@tauri-apps/plugin-dialog";
import { writeFile } from "@tauri-apps/plugin-fs";
import { useState } from "react";

import { ApiError } from "../api/client";
import { useAppServices } from "../AppContext";

/** Sales history + invoice reprint. Sales role sees only their own sales
 * (server-enforced by GET /sales); admin sees all. */
export default function Reports() {
  const { api } = useAppServices();
  const salesQuery = useQuery({ queryKey: ["sales"], queryFn: () => api.listSales() });
  const [error, setError] = useState<string | null>(null);
  const [busySaleId, setBusySaleId] = useState<string | null>(null);

  async function handleReprint(saleId: string, invoiceNumber: string) {
    setError(null);
    setBusySaleId(saleId);
    try {
      const path = await save({ defaultPath: `${invoiceNumber}.pdf`, filters: [{ name: "PDF", extensions: ["pdf"] }] });
      if (!path) return;
      const bytes = await api.getInvoicePdf(saleId);
      await writeFile(path, new Uint8Array(bytes));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : String(err));
    } finally {
      setBusySaleId(null);
    }
  }

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <Title2>Sales history</Title2>
      {error && <span style={{ color: "var(--colorPaletteRedForeground1)" }}>{error}</span>}
      <Table aria-label="Sales history">
        <TableHeader>
          <TableRow>
            <TableHeaderCell>Invoice</TableHeaderCell>
            <TableHeaderCell>Date</TableHeaderCell>
            <TableHeaderCell>Total</TableHeaderCell>
            <TableHeaderCell>Payment</TableHeaderCell>
            <TableHeaderCell></TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(salesQuery.data ?? []).map((sale) => (
            <TableRow key={sale.id}>
              <TableCell>{sale.invoice_number}</TableCell>
              <TableCell>{sale.created_at_client}</TableCell>
              <TableCell>{sale.total_amount}</TableCell>
              <TableCell>{sale.payment_mode}</TableCell>
              <TableCell>
                <Button
                  size="small"
                  disabled={busySaleId === sale.id}
                  onClick={() => handleReprint(sale.id, sale.invoice_number)}
                >
                  Reprint invoice PDF
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
