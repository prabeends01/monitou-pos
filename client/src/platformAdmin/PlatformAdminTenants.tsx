import {
  Badge,
  Body1,
  Button,
  Spinner,
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

import { useAppServices } from "../AppContext";
import PlatformAdminTenantDetail from "./PlatformAdminTenantDetail";

function statusColor(status: string): "success" | "danger" | "warning" | "informative" {
  if (status === "active" || status === "ACTIVE") return "success";
  if (status === "suspended") return "danger";
  if (status === "EXPIRED" || status === "GRACE_PERIOD") return "warning";
  return "informative";
}

export default function PlatformAdminTenants() {
  const { api } = useAppServices();
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(null);

  const tenantsQuery = useQuery({ queryKey: ["platform-tenants"], queryFn: () => api.listPlatformTenants() });

  if (selectedTenantId) {
    return <PlatformAdminTenantDetail tenantId={selectedTenantId} onBack={() => setSelectedTenantId(null)} />;
  }

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <Title2>Tenants</Title2>
      {tenantsQuery.isLoading ? (
        <Spinner label="Loading tenants…" />
      ) : (
        <Table aria-label="Tenants">
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Company</TableHeaderCell>
              <TableHeaderCell>Plan</TableHeaderCell>
              <TableHeaderCell>Users</TableHeaderCell>
              <TableHeaderCell>SKUs</TableHeaderCell>
              <TableHeaderCell>Subscription</TableHeaderCell>
              <TableHeaderCell>AMC renewal</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell />
            </TableRow>
          </TableHeader>
          <TableBody>
            {(tenantsQuery.data ?? []).map((tenant) => (
              <TableRow key={tenant.id}>
                <TableCell>
                  <Body1>{tenant.company_name}</Body1>
                  <div style={{ fontSize: 12, color: "var(--colorNeutralForeground3)" }}>{tenant.tenant_code}</div>
                </TableCell>
                <TableCell>{tenant.plan_code ?? "—"}</TableCell>
                <TableCell>
                  {tenant.users_used} / {tenant.users_max ?? "—"}
                </TableCell>
                <TableCell>
                  {tenant.skus_used} / {tenant.skus_max ?? "—"}
                </TableCell>
                <TableCell>{tenant.subscription_status ?? "—"}</TableCell>
                <TableCell>{tenant.amc_renewal_date ?? "—"}</TableCell>
                <TableCell>
                  <Badge appearance="tint" color={statusColor(tenant.tenant_status)}>
                    {tenant.tenant_status}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Button size="small" onClick={() => setSelectedTenantId(tenant.id)}>
                    View
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
