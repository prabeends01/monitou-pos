import {
  Badge,
  Body1,
  Body1Strong,
  Button,
  Caption1,
  Card,
  Dropdown,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  Option,
  Spinner,
  Switch,
  Checkbox,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Title2,
  Title3,
} from "@fluentui/react-components";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useAppServices } from "../AppContext";
import { ApiError } from "../api/client";

const PLAN_CODES = ["BASIC", "ESSENTIAL", "ENTERPRISE"];
const LIMIT_CODES = ["MAX_USERS", "MAX_BRANCHES", "MAX_WAREHOUSES", "MAX_SKUS"];

function ActionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card style={{ padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
      <Body1Strong>{title}</Body1Strong>
      {children}
    </Card>
  );
}

/** Every action here writes a `platform_audit_log` row server-side
 * (CLAUDE.md's AUDIT REQUIREMENT) — `reason` is required by the backend
 * (422 without one), so every form below requires it before enabling
 * submit, not just as a nice-to-have field. */
export default function PlatformAdminTenantDetail({ tenantId, onBack }: { tenantId: string; onBack: () => void }) {
  const { api } = useAppServices();
  const queryClient = useQueryClient();

  const detailQuery = useQuery({
    queryKey: ["platform-tenant", tenantId],
    queryFn: () => api.getPlatformTenantDetail(tenantId),
  });
  const auditQuery = useQuery({
    queryKey: ["platform-tenant-audit", tenantId],
    queryFn: () => api.getPlatformTenantAuditLog(tenantId),
  });

  const [error, setError] = useState<string | null>(null);
  const invalidate = () => {
    setError(null);
    queryClient.invalidateQueries({ queryKey: ["platform-tenant", tenantId] });
    queryClient.invalidateQueries({ queryKey: ["platform-tenant-audit", tenantId] });
    queryClient.invalidateQueries({ queryKey: ["platform-tenants"] });
  };
  const onErr = (err: unknown) => setError(err instanceof ApiError ? err.detail : String(err));

  const [planCode, setPlanCode] = useState("");
  const [planReason, setPlanReason] = useState("");
  const [planConfirmed, setPlanConfirmed] = useState(false);
  const impactQuery = useQuery({
    queryKey: ["platform-plan-impact", tenantId, planCode],
    queryFn: () => api.getPlanChangeImpact(tenantId, planCode),
    enabled: Boolean(planCode),
  });
  const impact = impactQuery.data;
  const hasImpact = Boolean(impact && (impact.exceeded_limits.length > 0 || impact.lost_features.length > 0));
  const changePlanMutation = useMutation({
    mutationFn: () => api.changeTenantPlan(tenantId, planCode, planReason, planConfirmed),
    onSuccess: () => {
      setPlanReason("");
      setPlanCode("");
      setPlanConfirmed(false);
      invalidate();
    },
    onError: onErr,
  });

  const [revokeReason, setRevokeReason] = useState("");
  const revokePlanMutation = useMutation({
    mutationFn: () => api.revokeTenantPlan(tenantId, revokeReason),
    onSuccess: () => {
      setRevokeReason("");
      invalidate();
    },
    onError: onErr,
  });

  const [featureCode, setFeatureCode] = useState("");
  const [featureEnabled, setFeatureEnabled] = useState(true);
  const [featureReason, setFeatureReason] = useState("");
  const overrideFeatureMutation = useMutation({
    mutationFn: () => api.overrideTenantFeature(tenantId, featureCode, featureEnabled, featureReason),
    onSuccess: () => {
      setFeatureReason("");
      invalidate();
    },
    onError: onErr,
  });

  const [limitCode, setLimitCode] = useState("");
  const [limitValue, setLimitValue] = useState("");
  const [limitReason, setLimitReason] = useState("");
  const overrideLimitMutation = useMutation({
    mutationFn: () => api.overrideTenantLimit(tenantId, limitCode, Number(limitValue), limitReason),
    onSuccess: () => {
      setLimitReason("");
      invalidate();
    },
    onError: onErr,
  });

  const [statusReason, setStatusReason] = useState("");
  const suspendMutation = useMutation({
    mutationFn: () => api.suspendTenant(tenantId, statusReason),
    onSuccess: () => {
      setStatusReason("");
      invalidate();
    },
    onError: onErr,
  });
  const reactivateMutation = useMutation({
    mutationFn: () => api.reactivateTenant(tenantId, statusReason),
    onSuccess: () => {
      setStatusReason("");
      invalidate();
    },
    onError: onErr,
  });

  const [renewalDate, setRenewalDate] = useState("");
  const [renewalReason, setRenewalReason] = useState("");
  const extendMutation = useMutation({
    mutationFn: () => api.extendTenantSubscription(tenantId, renewalDate, renewalReason),
    onSuccess: () => {
      setRenewalReason("");
      invalidate();
    },
    onError: onErr,
  });

  if (detailQuery.isLoading || !detailQuery.data) return <Spinner style={{ padding: 24 }} label="Loading tenant…" />;
  const tenant = detailQuery.data;
  const featureCodes = Object.keys(tenant.features).sort();

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16, maxWidth: 900 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Button appearance="secondary" size="small" onClick={onBack}>
          ← Back
        </Button>
        <Title2>{tenant.company_name}</Title2>
        <Badge appearance="tint" color={tenant.tenant_status === "active" ? "success" : "danger"}>
          {tenant.tenant_status}
        </Badge>
      </div>

      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}

      <Card style={{ padding: 16, display: "flex", flexWrap: "wrap", gap: 24 }}>
        <div>
          <Caption1>Tenant code</Caption1>
          <Body1Strong style={{ display: "block" }}>{tenant.tenant_code}</Body1Strong>
        </div>
        <div>
          <Caption1>Plan</Caption1>
          <Body1Strong style={{ display: "block" }}>{tenant.plan_name ?? "—"}</Body1Strong>
        </div>
        <div>
          <Caption1>Subscription status</Caption1>
          <Body1Strong style={{ display: "block" }}>{tenant.subscription_status ?? "—"}</Body1Strong>
        </div>
        <div>
          <Caption1>AMC start</Caption1>
          <Body1Strong style={{ display: "block" }}>{tenant.subscription_start_date ?? "—"}</Body1Strong>
        </div>
        <div>
          <Caption1>AMC renewal</Caption1>
          <Body1Strong style={{ display: "block" }}>{tenant.subscription_renewal_date ?? "—"}</Body1Strong>
        </div>
        <div>
          <Caption1>Annual AMC</Caption1>
          <Body1Strong style={{ display: "block" }}>{tenant.annual_amc ?? "—"}</Body1Strong>
        </div>
      </Card>

      <Card style={{ padding: 16 }}>
        <Body1Strong>Usage</Body1Strong>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 8 }}>
          {Object.entries(tenant.limits).map(([code, usage]) => (
            <div key={code}>
              <Caption1>{code}</Caption1>
              <Body1Strong style={{ display: "block" }}>
                {usage.used} / {usage.max}
              </Body1Strong>
            </div>
          ))}
        </div>
      </Card>

      <Card style={{ padding: 16 }}>
        <Body1Strong>Users ({tenant.users.length})</Body1Strong>
        <Table aria-label="Tenant users">
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Username</TableHeaderCell>
              <TableHeaderCell>Role</TableHeaderCell>
              <TableHeaderCell>Active</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tenant.users.map((u) => (
              <TableRow key={u.id}>
                <TableCell>{u.username}</TableCell>
                <TableCell>{u.role}</TableCell>
                <TableCell>{u.is_active ? "Yes" : "No"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Title3>Actions</Title3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <ActionCard title="Change plan">
          <Field label="New plan">
            <Dropdown
              value={planCode}
              selectedOptions={planCode ? [planCode] : []}
              onOptionSelect={(_, d) => {
                setPlanCode(d.optionValue ?? "");
                setPlanConfirmed(false);
              }}
            >
              {PLAN_CODES.map((code) => (
                <Option key={code} value={code}>
                  {code}
                </Option>
              ))}
            </Dropdown>
          </Field>
          <Field label="Reason">
            <Input value={planReason} onChange={(_, d) => setPlanReason(d.value)} />
          </Field>
          {impactQuery.isLoading && planCode && <Spinner size="tiny" label="Checking impact…" />}
          {hasImpact && impact && (
            <MessageBar intent={impact.is_downgrade ? "warning" : "info"}>
              <MessageBarBody>
                <Body1Strong style={{ display: "block", marginBottom: 4 }}>
                  {impact.is_downgrade ? "This is a downgrade" : "This change"} affects existing access:
                </Body1Strong>
                {impact.exceeded_limits.map((l) => (
                  <div key={l.limit_code}>
                    {l.limit_code}: {l.current_usage} in use, new limit is {l.new_limit} — no new ones can be
                    created until usage is back under the cap.
                  </div>
                ))}
                {impact.lost_features.length > 0 && (
                  <div>Features lost: {impact.lost_features.map((f) => f.name).join(", ")}</div>
                )}
                <div style={{ marginTop: 8 }}>
                  <Checkbox
                    label="I understand — no data is deleted, but access above will be restricted"
                    checked={planConfirmed}
                    onChange={(_, d) => setPlanConfirmed(Boolean(d.checked))}
                  />
                </div>
              </MessageBarBody>
            </MessageBar>
          )}
          <Button
            appearance="primary"
            disabled={
              !planCode ||
              !planReason ||
              changePlanMutation.isPending ||
              impactQuery.isLoading ||
              (hasImpact && !planConfirmed)
            }
            onClick={() => changePlanMutation.mutate()}
          >
            Change plan
          </Button>
        </ActionCard>

        <ActionCard title="Revoke plan">
          <Body1>
            Clears the plan entirely — the tenant can still log in, but loses every plan-gated feature immediately.
            No data is deleted. Not the same as suspending the account.
          </Body1>
          <Field label="Reason">
            <Input value={revokeReason} onChange={(_, d) => setRevokeReason(d.value)} />
          </Field>
          <Button
            appearance="primary"
            disabled={!tenant.plan_code || !revokeReason || revokePlanMutation.isPending}
            onClick={() => revokePlanMutation.mutate()}
          >
            {tenant.plan_code ? `Revoke ${tenant.plan_code}` : "No active plan"}
          </Button>
        </ActionCard>

        <ActionCard title="Feature override">
          <Field label="Feature">
            <Dropdown
              value={featureCode}
              selectedOptions={featureCode ? [featureCode] : []}
              onOptionSelect={(_, d) => setFeatureCode(d.optionValue ?? "")}
            >
              {featureCodes.map((code) => (
                <Option key={code} value={code}>
                  {code}
                </Option>
              ))}
            </Dropdown>
          </Field>
          <Switch
            label={featureEnabled ? "Grant this feature" : "Revoke this feature"}
            checked={featureEnabled}
            onChange={(_, d) => setFeatureEnabled(d.checked)}
          />
          <Field label="Reason">
            <Input value={featureReason} onChange={(_, d) => setFeatureReason(d.value)} />
          </Field>
          <Button
            appearance="primary"
            disabled={!featureCode || !featureReason || overrideFeatureMutation.isPending}
            onClick={() => overrideFeatureMutation.mutate()}
          >
            Apply override
          </Button>
        </ActionCard>

        <ActionCard title="Limit override">
          <Field label="Limit">
            <Dropdown
              value={limitCode}
              selectedOptions={limitCode ? [limitCode] : []}
              onOptionSelect={(_, d) => setLimitCode(d.optionValue ?? "")}
            >
              {LIMIT_CODES.map((code) => (
                <Option key={code} value={code}>
                  {code}
                </Option>
              ))}
            </Dropdown>
          </Field>
          <Field label="New value">
            <Input value={limitValue} onChange={(_, d) => setLimitValue(d.value)} type="number" />
          </Field>
          <Field label="Reason">
            <Input value={limitReason} onChange={(_, d) => setLimitReason(d.value)} />
          </Field>
          <Button
            appearance="primary"
            disabled={!limitCode || !limitValue || !limitReason || overrideLimitMutation.isPending}
            onClick={() => overrideLimitMutation.mutate()}
          >
            Apply override
          </Button>
        </ActionCard>

        <ActionCard title={tenant.tenant_status === "active" ? "Suspend tenant" : "Reactivate tenant"}>
          <Field label="Reason">
            <Input value={statusReason} onChange={(_, d) => setStatusReason(d.value)} />
          </Field>
          {tenant.tenant_status === "active" ? (
            <Button
              appearance="primary"
              disabled={!statusReason || suspendMutation.isPending}
              onClick={() => suspendMutation.mutate()}
            >
              Suspend
            </Button>
          ) : (
            <Button
              appearance="primary"
              disabled={!statusReason || reactivateMutation.isPending}
              onClick={() => reactivateMutation.mutate()}
            >
              Reactivate
            </Button>
          )}
        </ActionCard>

        <ActionCard title="Extend subscription">
          <Field label="New AMC renewal date">
            <Input type="date" value={renewalDate} onChange={(_, d) => setRenewalDate(d.value)} />
          </Field>
          <Field label="Reason">
            <Input value={renewalReason} onChange={(_, d) => setRenewalReason(d.value)} />
          </Field>
          <Button
            appearance="primary"
            disabled={!renewalDate || !renewalReason || extendMutation.isPending}
            onClick={() => extendMutation.mutate()}
          >
            Extend
          </Button>
        </ActionCard>
      </div>

      <Title3>Audit log</Title3>
      <Table aria-label="Tenant audit log">
        <TableHeader>
          <TableRow>
            <TableHeaderCell>When</TableHeaderCell>
            <TableHeaderCell>Admin</TableHeaderCell>
            <TableHeaderCell>Action</TableHeaderCell>
            <TableHeaderCell>Old</TableHeaderCell>
            <TableHeaderCell>New</TableHeaderCell>
            <TableHeaderCell>Reason</TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(auditQuery.data ?? []).map((entry) => (
            <TableRow key={entry.id}>
              <TableCell>{new Date(entry.created_at).toLocaleString()}</TableCell>
              <TableCell>{entry.platform_admin_username}</TableCell>
              <TableCell>{entry.action}</TableCell>
              <TableCell>{entry.old_value ? JSON.stringify(entry.old_value) : "—"}</TableCell>
              <TableCell>{entry.new_value ? JSON.stringify(entry.new_value) : "—"}</TableCell>
              <TableCell>{entry.reason ?? "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
