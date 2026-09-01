import {
  Body1Strong,
  Caption1,
  Card,
  Dropdown,
  Option,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Title2,
} from "@fluentui/react-components";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useAppServices } from "../AppContext";
import FeatureGate from "../components/FeatureGate";
import type { StockMoverEntry } from "../types";

const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes, per CLAUDE.md Section 5.8
const PERIODS = ["daily", "weekly", "monthly"] as const;
const LOOKBACK_DAYS: Record<(typeof PERIODS)[number], number> = { daily: 30, weekly: 90, monthly: 365 };

function StatCard({ title, value }: { title: string; value: string }) {
  return (
    <Card style={{ padding: 12, flex: 1 }}>
      <Caption1>{title}</Caption1>
      <Body1Strong style={{ fontSize: 20 }}>{value}</Body1Strong>
    </Card>
  );
}

function MoverTable({ title, entries }: { title: string; entries: StockMoverEntry[] }) {
  return (
    <Card style={{ padding: 12, flex: 1 }}>
      <Body1Strong>{title}</Body1Strong>
      <Table aria-label={title} size="small">
        <TableHeader>
          <TableRow>
            <TableHeaderCell>SKU</TableHeaderCell>
            <TableHeaderCell>Name</TableHeaderCell>
            <TableHeaderCell>Sold (30d)</TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map((entry) => (
            <TableRow key={entry.product_id}>
              <TableCell>{entry.sku}</TableCell>
              <TableCell>{entry.name}</TableCell>
              <TableCell>{entry.qty_sold_30d}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

/** Admin home: sales-summary chart, stock-stats cards, low-stock-alerts
 * table. Calls the three Section 5.8 report endpoints on load and on a
 * periodic refresh while the screen is open. */
export default function Dashboard() {
  const { api } = useAppServices();
  const [period, setPeriod] = useState<(typeof PERIODS)[number]>("daily");

  const salesQuery = useQuery({
    queryKey: ["sales-summary", period],
    queryFn: () => {
      const to = new Date();
      const from = new Date(to.getTime() - LOOKBACK_DAYS[period] * 86400_000);
      return api.salesSummary(period, from.toISOString(), to.toISOString());
    },
    refetchInterval: REFRESH_INTERVAL_MS,
  });

  const stockStatsQuery = useQuery({
    queryKey: ["stock-stats"],
    queryFn: () => api.stockStats(),
    refetchInterval: REFRESH_INTERVAL_MS,
  });

  const lowStockQuery = useQuery({
    queryKey: ["low-stock-alerts"],
    queryFn: () => api.lowStockAlerts(),
    refetchInterval: REFRESH_INTERVAL_MS,
  });

  const chartData = (salesQuery.data ?? []).map((bucket) => ({
    period: bucket.period_start.slice(0, 10),
    total_sales: Number(bucket.total_sales),
  }));

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Title2>Sales summary</Title2>
        <Dropdown
          value={period}
          selectedOptions={[period]}
          onOptionSelect={(_, d) => setPeriod((d.optionValue as (typeof PERIODS)[number]) ?? "daily")}
        >
          {PERIODS.map((p) => (
            <Option key={p} value={p}>
              {p}
            </Option>
          ))}
        </Dropdown>
      </div>

      <div style={{ height: 250 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="period" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="total_sales" fill="#0f6cbd" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <StatCard title="Total SKUs" value={String(stockStatsQuery.data?.total_skus ?? "—")} />
        <StatCard title="Stock value" value={stockStatsQuery.data?.total_stock_value ?? "—"} />
        <StatCard title="Out of stock" value={String(stockStatsQuery.data?.out_of_stock_count ?? "—")} />
        <StatCard title="Below threshold" value={String(stockStatsQuery.data?.below_threshold_count ?? "—")} />
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <FeatureGate feature="FAST_MOVING_ANALYSIS">
          <MoverTable title="Fastest moving" entries={stockStatsQuery.data?.fastest_moving ?? []} />
        </FeatureGate>
        <FeatureGate feature="SLOW_MOVING_ANALYSIS">
          <MoverTable title="Slowest moving" entries={stockStatsQuery.data?.slowest_moving ?? []} />
        </FeatureGate>
      </div>

      <Title2>Low stock — needs reordering</Title2>
      <Table aria-label="Low stock alerts">
        <TableHeader>
          <TableRow>
            <TableHeaderCell>SKU</TableHeaderCell>
            <TableHeaderCell>Name</TableHeaderCell>
            <TableHeaderCell>Balance</TableHeaderCell>
            <TableHeaderCell>Reorder threshold</TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(lowStockQuery.data ?? []).map((alert) => (
            <TableRow key={alert.product_id}>
              <TableCell>{alert.sku}</TableCell>
              <TableCell>{alert.name}</TableCell>
              <TableCell>{alert.balance}</TableCell>
              <TableCell>{alert.reorder_threshold}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
