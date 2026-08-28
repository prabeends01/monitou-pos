import {
  Badge,
  Body1,
  Button,
  Caption1,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  MessageBar,
  MessageBarBody,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Textarea,
  Title2,
  Title3,
  tokens,
} from "@fluentui/react-components";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";

import { ApiError } from "../api/client";
import { useAppServices } from "../AppContext";

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

/** Settings > Plan & Subscription > "View plans" / "Request upgrade" —
 * CLAUDE.md Stage 10. Requesting an upgrade only creates a review request
 * (`POST /tenant/me/upgrade-requests`) — it never changes the tenant's
 * plan directly; that's Platform Admin's call (Stage 11+). */
export default function PlanComparison({ onBack }: { onBack: () => void }) {
  const { api } = useAppServices();
  const queryClient = useQueryClient();
  const [targetPlan, setTargetPlan] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const comparisonQuery = useQuery({ queryKey: ["plan-comparison"], queryFn: () => api.getPlanComparison() });
  const requestsQuery = useQuery({ queryKey: ["upgrade-requests"], queryFn: () => api.listUpgradeRequests() });

  const requestMutation = useMutation({
    mutationFn: () => api.requestUpgrade(targetPlan as string, note || undefined),
    onSuccess: () => {
      setTargetPlan(null);
      setNote("");
      queryClient.invalidateQueries({ queryKey: ["upgrade-requests"] });
    },
  });

  if (comparisonQuery.isLoading) return <Spinner style={{ padding: 24 }} label="Loading plans…" />;
  if (comparisonQuery.isError || !comparisonQuery.data) {
    return (
      <div style={{ padding: 16 }}>
        <MessageBar intent="error">
          <MessageBarBody>Couldn't load plan comparison. Try again shortly.</MessageBarBody>
        </MessageBar>
      </div>
    );
  }

  const { plans, features } = comparisonQuery.data;
  const pendingByPlan = new Set(
    (requestsQuery.data ?? []).filter((r) => r.status === "pending").map((r) => r.requested_plan_code),
  );

  const modules = [...new Set(features.map((f) => f.module))];

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Button appearance="secondary" size="small" onClick={onBack}>
          ← Back
        </Button>
        <Title2>Compare plans</Title2>
      </div>

      <div style={{ overflowX: "auto" }}>
        <Table aria-label="Plan comparison">
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Capability</TableHeaderCell>
              {plans.map((plan) => (
                <TableHeaderCell key={plan.code}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Title3>{plan.name}</Title3>
                      {plan.is_current && (
                        <Badge appearance="filled" color="brand">
                          Current plan
                        </Badge>
                      )}
                      {plan.is_recommended && !plan.is_current && (
                        <Badge appearance="tint" color="success">
                          Recommended
                        </Badge>
                      )}
                    </div>
                  </div>
                </TableHeaderCell>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell>
                <Body1>Initial setup</Body1>
              </TableCell>
              {plans.map((plan) => (
                <TableCell key={plan.code}>{formatCurrency(plan.setup_price)}</TableCell>
              ))}
            </TableRow>
            <TableRow>
              <TableCell>
                <Body1>Annual Managed AMC</Body1>
              </TableCell>
              {plans.map((plan) => (
                <TableCell key={plan.code}>{formatCurrency(plan.annual_amc)}</TableCell>
              ))}
            </TableRow>
            <TableRow style={{ backgroundColor: tokens.colorNeutralBackground2 }}>
              <TableCell colSpan={1 + plans.length}>
                <Body1 style={{ fontWeight: 600 }}>Actions</Body1>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell />
              {plans.map((plan) => (
                <TableCell key={plan.code}>
                  {plan.is_current ? (
                    <Caption1>You're on this plan</Caption1>
                  ) : pendingByPlan.has(plan.code) ? (
                    <Badge appearance="tint" color="warning">
                      Upgrade requested
                    </Badge>
                  ) : (
                    <Button size="small" appearance="primary" onClick={() => setTargetPlan(plan.code)}>
                      Request upgrade
                    </Button>
                  )}
                </TableCell>
              ))}
            </TableRow>

            {modules.map((module) => (
              <Fragment key={module}>
                <TableRow style={{ backgroundColor: tokens.colorNeutralBackground2 }}>
                  <TableCell colSpan={1 + plans.length}>
                    <Caption1 style={{ fontWeight: 600 }}>{moduleLabel(module)}</Caption1>
                  </TableCell>
                </TableRow>
                {features
                  .filter((f) => f.module === module)
                  .map((feature) => (
                    <TableRow key={feature.code}>
                      <TableCell>{feature.name}</TableCell>
                      {plans.map((plan) => (
                        <TableCell key={plan.code}>
                          {feature.enabled_by_plan[plan.code] ? (
                            <span style={{ color: tokens.colorPaletteGreenForeground1 }}>✓</span>
                          ) : (
                            <span style={{ color: tokens.colorNeutralForeground4 }}>—</span>
                          )}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
              </Fragment>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={targetPlan !== null} onOpenChange={(_, data) => !data.open && setTargetPlan(null)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Request upgrade to {targetPlan}</DialogTitle>
            <DialogContent style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <Body1>
                This sends a request for review — it doesn't change your plan automatically. Someone from our team
                will follow up.
              </Body1>
              <Textarea
                placeholder="Anything we should know? (optional)"
                value={note}
                onChange={(_, d) => setNote(d.value)}
              />
              {requestMutation.isError && (
                <MessageBar intent="error">
                  <MessageBarBody>
                    {requestMutation.error instanceof ApiError
                      ? requestMutation.error.detail
                      : String(requestMutation.error)}
                  </MessageBarBody>
                </MessageBar>
              )}
            </DialogContent>
            <DialogActions>
              <Button appearance="secondary" onClick={() => setTargetPlan(null)}>
                Cancel
              </Button>
              <Button appearance="primary" disabled={requestMutation.isPending} onClick={() => requestMutation.mutate()}>
                Send request
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
}
