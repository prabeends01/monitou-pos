import { useQuery } from "@tanstack/react-query";

import { useAppServices } from "../AppContext";
import type { FeatureInfo, LimitUsage, TenantEntitlements } from "../types";

// Entitlements change on a plan/override change (a platform-admin action,
// or an upgrade taking effect) — not on every render, so a long staleTime
// is correct here, unlike Dashboard's REFRESH_INTERVAL_MS polling.
const STALE_TIME_MS = 5 * 60 * 1000;

/** The one place the frontend fetches plan/feature/limit state. Every
 * screen goes through this (or useFeature/useLimit below) — never call
 * api.getEntitlements() directly from a component, so there's exactly one
 * cached snapshot per session. */
export function useEntitlements() {
  const { api } = useAppServices();
  return useQuery({
    queryKey: ["entitlements"],
    queryFn: () => api.getEntitlements(),
    staleTime: STALE_TIME_MS,
  });
}

/** True only once the entitlements snapshot has loaded and says so.
 * Fails closed while loading or on error — matching the backend's own
 * default-deny (CLAUDE.md Section 11.3), never assume access is granted
 * just because we don't know yet. */
export function useFeature(code: string): boolean {
  const { data } = useEntitlements();
  return data?.features[code] ?? false;
}

export function useFeatureInfo(code: string): FeatureInfo | undefined {
  const { data } = useEntitlements();
  return data?.feature_info[code];
}

export function useLimit(code: string): LimitUsage | undefined {
  const { data } = useEntitlements();
  return data?.limits[code];
}

/** Pure resolution logic pulled out of the hook so it's testable without
 * rendering — see hooks/useEntitlements.test.ts. Fluent UI's `FeatureGate`
 * component itself hits the same jsdom/tabster issue noted in CLAUDE.md
 * Phase 8 that blocks render-testing other Fluent screens in this repo. */
export function resolveFeature(entitlements: TenantEntitlements | undefined, code: string): boolean {
  return entitlements?.features[code] ?? false;
}
