import {
  Badge,
  Body1,
  Body1Strong,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Input,
  MessageBar,
  MessageBarBody,
  Spinner,
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

import { useAppServices } from "../AppContext";
import { ApiError } from "../api/client";
import type { PlatformTenantDetail, PlatformUpgradeRequestRow } from "../types";

type Action = { kind: "approve" | "reject"; request: PlatformUpgradeRequestRow };

/** Platform Admin's cross-tenant upgrade-request inbox — without this, a
 * request only ever surfaced if an admin happened to open that exact
 * tenant and change its plan themselves. See CLAUDE.md Stage 10/11. */
export default function PlatformAdminUpgradeRequests() {
  const { api } = useAppServices();
  const queryClient = useQueryClient();
  const [action, setAction] = useState<Action | null>(null);
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const requestsQuery = useQuery({
    queryKey: ["platform-upgrade-requests"],
    queryFn: () => api.listPlatformUpgradeRequests(),
  });

  const impactQuery = useQuery({
    queryKey: ["platform-plan-impact", action?.request.tenant_id, action?.request.requested_plan_code],
    queryFn: () => api.getPlanChangeImpact(action!.request.tenant_id, action!.request.requested_plan_code),
    enabled: action?.kind === "approve",
  });
  const impact = impactQuery.data;
  const hasImpact = Boolean(impact && (impact.exceeded_limits.length > 0 || impact.lost_features.length > 0));

  const decideMutation = useMutation<PlatformTenantDetail | PlatformUpgradeRequestRow, unknown, void>({
    mutationFn: () => {
      if (!action) throw new Error("no action selected");
      return action.kind === "approve"
        ? api.approveUpgradeRequest(action.request.id, reason, confirmed)
        : api.rejectUpgradeRequest(action.request.id, reason);
    },
    onSuccess: () => {
      closeDialog();
      queryClient.invalidateQueries({ queryKey: ["platform-upgrade-requests"] });
      queryClient.invalidateQueries({ queryKey: ["platform-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["platform-tenants"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.detail : String(err)),
  });

  function closeDialog() {
    setAction(null);
    setReason("");
    setConfirmed(false);
    setError(null);
  }

  const requests = requestsQuery.data ?? [];

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <Title2>Upgrade requests</Title2>
      {requestsQuery.isLoading ? (
        <Spinner label="Loading requests…" />
      ) : requests.length === 0 ? (
        <Body1>No pending upgrade requests.</Body1>
      ) : (
        <Table aria-label="Pending upgrade requests">
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Company</TableHeaderCell>
              <TableHeaderCell>Requested plan</TableHeaderCell>
              <TableHeaderCell>Requested by</TableHeaderCell>
              <TableHeaderCell>Note</TableHeaderCell>
              <TableHeaderCell>Requested</TableHeaderCell>
              <TableHeaderCell />
            </TableRow>
          </TableHeader>
          <TableBody>
            {requests.map((req) => (
              <TableRow key={req.id}>
                <TableCell>
                  <Body1>{req.company_name}</Body1>
                  <div style={{ fontSize: 12, color: "var(--colorNeutralForeground3)" }}>{req.tenant_code}</div>
                </TableCell>
                <TableCell>
                  <Badge appearance="tint" color="brand">
                    {req.requested_plan_code}
                  </Badge>
                </TableCell>
                <TableCell>{req.requested_by_username ?? "—"}</TableCell>
                <TableCell>{req.note ?? "—"}</TableCell>
                <TableCell>{new Date(req.requested_at).toLocaleDateString()}</TableCell>
                <TableCell>
                  <div style={{ display: "flex", gap: 6 }}>
                    <Button size="small" appearance="primary" onClick={() => setAction({ kind: "approve", request: req })}>
                      Approve
                    </Button>
                    <Button size="small" onClick={() => setAction({ kind: "reject", request: req })}>
                      Reject
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Dialog open={action !== null} onOpenChange={(_, d) => !d.open && closeDialog()}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>
              {action?.kind === "approve" ? "Approve" : "Reject"} upgrade to {action?.request.requested_plan_code}
            </DialogTitle>
            <DialogContent style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <Body1>{action?.request.company_name}</Body1>
              <Input placeholder="Reason (required)" value={reason} onChange={(_, d) => setReason(d.value)} />
              {action?.kind === "approve" && impactQuery.isLoading && <Spinner size="tiny" label="Checking impact…" />}
              {action?.kind === "approve" && hasImpact && impact && (
                <MessageBar intent={impact.is_downgrade ? "warning" : "info"}>
                  <MessageBarBody>
                    <Body1Strong style={{ display: "block", marginBottom: 4 }}>This change affects existing access:</Body1Strong>
                    {impact.exceeded_limits.map((l) => (
                      <div key={l.limit_code}>
                        {l.limit_code}: {l.current_usage} in use, new limit is {l.new_limit}
                      </div>
                    ))}
                    {impact.lost_features.length > 0 && (
                      <div>Features lost: {impact.lost_features.map((f) => f.name).join(", ")}</div>
                    )}
                    <div style={{ marginTop: 8 }}>
                      <Checkbox
                        label="I understand — no data is deleted, but access above will be restricted"
                        checked={confirmed}
                        onChange={(_, d) => setConfirmed(Boolean(d.checked))}
                      />
                    </div>
                  </MessageBarBody>
                </MessageBar>
              )}
              {error && (
                <MessageBar intent="error">
                  <MessageBarBody>{error}</MessageBarBody>
                </MessageBar>
              )}
            </DialogContent>
            <DialogActions>
              <Button appearance="secondary" onClick={closeDialog}>
                Cancel
              </Button>
              <Button
                appearance="primary"
                disabled={
                  !reason ||
                  decideMutation.isPending ||
                  (action?.kind === "approve" && (impactQuery.isLoading || (hasImpact && !confirmed)))
                }
                onClick={() => decideMutation.mutate()}
              >
                {action?.kind === "approve" ? "Approve" : "Reject"}
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
}
