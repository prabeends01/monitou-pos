import { Body1, Button, Caption1, Card, Tooltip, makeStyles, tokens } from "@fluentui/react-components";
import { cloneElement, isValidElement } from "react";
import type { ReactElement, ReactNode } from "react";

import { useFeature, useFeatureInfo } from "../hooks/useEntitlements";
import LockIcon from "./LockIcon";

const useStyles = makeStyles({
  card: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    padding: "16px",
    alignItems: "flex-start",
    maxWidth: "360px",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    color: tokens.colorNeutralForeground3,
  },
});

type FeatureGateMode = "hide" | "lock" | "disable";

interface FeatureGateProps {
  feature: string;
  mode?: FeatureGateMode;
  children: ReactNode;
  /** Wired up once the Plan & Subscription / upgrade-comparison screens
   * exist (Stage 9/10) — until then the CTA renders but has nothing to
   * navigate to yet, so this stays optional rather than guessing a route. */
  onUpgradeClick?: () => void;
}

/** Central plan-gating for the UI. Never spread `useFeature(...)` checks
 * and ad hoc locked-state markup through individual screens — wrap the
 * gated content in this instead, so every locked feature looks and
 * behaves the same way. Backend `require_feature` is still the real
 * enforcement (CLAUDE.md Section 11.6/11.7) — this is UX only. */
export default function FeatureGate({ feature, mode = "lock", children, onUpgradeClick }: FeatureGateProps) {
  const styles = useStyles();
  const enabled = useFeature(feature);
  const info = useFeatureInfo(feature);

  if (enabled) return <>{children}</>;

  if (mode === "hide") return null;

  if (mode === "disable") {
    const message = info?.message ?? "This feature isn't available on your current plan.";
    if (isValidElement(children)) {
      const disabledChild = cloneElement(children as ReactElement<{ disabled?: boolean }>, { disabled: true });
      return <Tooltip content={message} relationship="label">{disabledChild}</Tooltip>;
    }
    return (
      <Tooltip content={message} relationship="label">
        <span>{children}</span>
      </Tooltip>
    );
  }

  // mode === "lock"
  return (
    <Card className={styles.card}>
      <div className={styles.header}>
        <LockIcon />
        <Caption1>{info?.required_plan ? `Requires ${titleCase(info.required_plan)}` : "Plan upgrade required"}</Caption1>
      </div>
      <Body1>{info?.message ?? "This feature isn't available on your current plan."}</Body1>
      <Button appearance="primary" size="small" onClick={onUpgradeClick} disabled={!onUpgradeClick}>
        View plans
      </Button>
    </Card>
  );
}

function titleCase(code: string): string {
  return code.charAt(0) + code.slice(1).toLowerCase();
}
