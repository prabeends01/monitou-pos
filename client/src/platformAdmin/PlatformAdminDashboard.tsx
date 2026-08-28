import { Body1Strong, Card, Caption1, Spinner, Title2 } from "@fluentui/react-components";
import { useQuery } from "@tanstack/react-query";

import { useAppServices } from "../AppContext";

function StatCard({ title, value }: { title: string; value: number }) {
  return (
    <Card style={{ padding: 14, minWidth: 160 }}>
      <Caption1>{title}</Caption1>
      <Body1Strong style={{ display: "block", fontSize: 24 }}>{value.toLocaleString()}</Body1Strong>
    </Card>
  );
}

export default function PlatformAdminDashboard() {
  const { api } = useAppServices();
  const { data, isLoading } = useQuery({ queryKey: ["platform-dashboard"], queryFn: () => api.getPlatformDashboard() });

  if (isLoading || !data) return <Spinner style={{ padding: 24 }} label="Loading dashboard…" />;

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
      <Title2>Platform overview</Title2>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
        <StatCard title="Total tenants" value={data.total_tenants} />
        <StatCard title="Active tenants" value={data.active_tenants} />
        <StatCard title="Basic customers" value={data.basic_customers} />
        <StatCard title="Essential customers" value={data.essential_customers} />
        <StatCard title="Enterprise customers" value={data.enterprise_customers} />
        <StatCard title="AMC due" value={data.amc_due} />
        <StatCard title="Upcoming renewals" value={data.upcoming_renewals} />
        <StatCard title="Suspended accounts" value={data.suspended_accounts} />
        <StatCard title="Pending upgrade requests" value={data.pending_upgrade_requests} />
      </div>
    </div>
  );
}
