import { create } from "zustand";

import type { ApiClient } from "../api/client";

/** Entirely separate from sessionStore.ts's tenant session (CLAUDE.md
 * Section 11.9.6/Stage 11) — a platform admin is never "a tenant user with
 * more permissions," it's a different credential space end to end. No
 * persistence (unlike the tenant session's plugin-store save) — a platform
 * operator re-authenticates every launch, deliberately, since this is an
 * internal ops surface, not something to stay silently logged into. */
interface PlatformAdminState {
  username: string | null;
  loggedOutReason: string | null;
  loggedIn: (username: string) => void;
  logOut: (api: ApiClient, reason?: string) => void;
  clearLoggedOutReason: () => void;
}

export const usePlatformAdminStore = create<PlatformAdminState>((set) => ({
  username: null,
  loggedOutReason: null,
  loggedIn: (username) => set({ username, loggedOutReason: null }),
  logOut: (api, reason) => {
    api.platformAdminLogout();
    set({ username: null, loggedOutReason: reason ?? null });
  },
  clearLoggedOutReason: () => set({ loggedOutReason: null }),
}));
