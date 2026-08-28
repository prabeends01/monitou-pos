import { describe, expect, it } from "vitest";

import { resolveFeature } from "./useEntitlements";
import type { TenantEntitlements } from "../types";

function entitlements(overrides: Partial<TenantEntitlements> = {}): TenantEntitlements {
  return {
    tenant_code: "T1",
    company_name: "Test Co",
    plan_code: "BASIC",
    plan_name: "Basic",
    tenant_status: "active",
    features: { PRODUCT_MASTER: true, BARCODE_GENERATION: false },
    feature_info: {
      BARCODE_GENERATION: {
        name: "Barcode Generation",
        module: "barcode",
        required_plan: "ESSENTIAL",
        message: "Barcode Generation is available in Essential and Enterprise plans.",
      },
    },
    subscription: null,
    limits: {},
    ...overrides,
  };
}

describe("resolveFeature", () => {
  it("returns true for an enabled feature", () => {
    expect(resolveFeature(entitlements(), "PRODUCT_MASTER")).toBe(true);
  });

  it("returns false for a disabled feature", () => {
    expect(resolveFeature(entitlements(), "BARCODE_GENERATION")).toBe(false);
  });

  it("fails closed for a feature code missing from the snapshot", () => {
    expect(resolveFeature(entitlements(), "SOME_FUTURE_FEATURE")).toBe(false);
  });

  it("fails closed when the snapshot hasn't loaded yet", () => {
    expect(resolveFeature(undefined, "PRODUCT_MASTER")).toBe(false);
  });
});
