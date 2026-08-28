import {
  Badge,
  Body1Strong,
  Button,
  Caption1,
  Card,
  MessageBar,
  MessageBarBody,
  ProgressBar,
  Spinner,
  Title2,
  Title3,
} from "@fluentui/react-components";
import { useState } from "react";

import { useEntitlements } from "../hooks/useEntitlements";
import PlanComparison from "./PlanComparison";

const LIMIT_LABELS: Record<string, string> = {
  MAX_USERS: "Users",
  MAX_BRANCHES: "Branches",
  MAX_WAREHOUSES: "Warehouses",
  MAX_SKUS: "SKUs",
};

// Fixed display order — matches the spec's Plan & Subscription page layout
// (Users, Warehouses, Branches, SKUs), not the arbitrary key order the API
// happens to return.
const LIMIT_ORDER = ["MAX_USERS", "MAX_WAREHOUSES", "MAX_BRANCHES", "MAX_SKUS"];

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatCurrency(value: string): string {
  const n = Number(value);
  return Number.isFinite(n) ? `₹${n.toLocaleString("en-IN")}` : value;
}

function moduleLabel(module: string): string {
  return module
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** Settings > Plan & Subscription — CLAUDE.md Stage 9. Read-only display of
 * the tenant's current plan, subscription term, usage against limits, and
 * enabled capabilities, plus "View Plans" / "Request Upgrade" entry points
 * into Stage 10's comparison screen. Neither button changes the plan
 * directly (Section 13: upgrades/downgrades are never automatic). */
export default function PlanSubscription() {
  const { data, isLoading, isError } = useEntitlements();
  const [showComparison, setShowComparison] = useState(false);

  if (showComparison) return <PlanComparison onBack={() => setShowComparison(false)} />;

  if (isLoading) return <Spinner style={{ padding: 24 }} label="Loading plan details…" />;
  if (isError || !data) {
    return (
      <div style={{ padding: 16 }}>
        <MessageBar intent="error">
          <MessageBarBody>Couldn't load plan & subscription details. Try again shortly.</MessageBarBody>
        </MessageBar>
      </div>
    );
  }

  const enabledByModule = new Map<string, string[]>();
  for (const [code, enabled] of Object.entries(data.features)) {
    if (!enabled) continue;
    const info = data.feature_info[code];
    if (!info) continue;
    const list = enabledByModule.get(info.module) ?? [];
    list.push(info.name);
    enabledByModule.set(info.module, list);
  }

  const limitCodes = [
    ...LIMIT_ORDER.filter((c) => c in data.limits),
    ...Object.keys(data.limits).filter((c) => !LIMIT_ORDER.includes(c)),
  ];

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16, maxWidth: 720 }}>
      <Title2>Plan & Subscription</Title2>

      <Card style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Title3>{data.plan_name ?? "No active plan"}</Title3>
          {data.plan_code && <Badge appearance="tint" color="brand">{data.plan_code}</Badge>}
        </div>
        <Caption1>{data.company_name} · {data.tenant_code}</Caption1>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 8 }}>
          <div>
            <Caption1>Account status</Caption1>
            <Body1Strong style={{ display: "block", textTransform: "capitalize" }}>{data.tenant_status}</Body1Strong>
          </div>
          <div>
            <Caption1>Subscription status</Caption1>
            <Body1Strong style={{ display: "block" }}>{data.subscription?.status ?? "—"}</Body1Strong>
          </div>
          <div>
            <Caption1>AMC start date</Caption1>
            <Body1Strong style={{ display: "block" }}>{formatDate(data.subscription?.start_date ?? null)}</Body1Strong>
          </div>
          <div>
            <Caption1>AMC renewal date</Caption1>
            <Body1Strong style={{ display: "block" }}>
              {formatDate(data.subscription?.renewal_date ?? null)}
            </Body1Strong>
          </div>
          {data.subscription && (
            <div>
              <Caption1>Annual AMC</Caption1>
              <Body1Strong style={{ display: "block" }}>{formatCurrency(data.subscription.annual_amc)}</Body1Strong>
            </div>
          )}
        </div>
      </Card>

      <Card style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        <Body1Strong>Usage</Body1Strong>
        {limitCodes.map((code) => {
          const { used, max } = data.limits[code];
          const ratio = max > 0 ? Math.min(1, used / max) : 0;
          return (
            <div key={code} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <Caption1>{LIMIT_LABELS[code] ?? code}</Caption1>
                <Caption1>
                  {used.toLocaleString()} / {max.toLocaleString()}
                </Caption1>
              </div>
              <ProgressBar value={ratio} color={ratio >= 1 ? "error" : ratio >= 0.8 ? "warning" : "brand"} />
            </div>
          );
        })}
      </Card>

      <Card style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
        <Body1Strong>Enabled capabilities</Body1Strong>
        {[...enabledByModule.entries()].map(([module, names]) => (
          <div key={module} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <Caption1>{moduleLabel(module)}</Caption1>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {names.map((name) => (
                <Badge key={name} appearance="outline" size="small">
                  {name}
                </Badge>
              ))}
            </div>
          </div>
        ))}
      </Card>

      <div style={{ display: "flex", gap: 8 }}>
        <Button appearance="secondary" onClick={() => setShowComparison(true)}>
          View plans
        </Button>
        <Button appearance="primary" onClick={() => setShowComparison(true)}>
          Request upgrade
        </Button>
      </div>
    </div>
  );
}
