import { create } from "zustand";

import type { ApiClient } from "../api/client";
import { clearSession } from "../session";
import type { Role } from "../types";

interface SessionState {
  role: Role | null;
  username: string | null;
  /** Set when the app force-logs-out due to a 401 (e.g. the backend's
   * database was reset, invalidating the saved session) — shown once on
   * the login screen so it's clear *why*, not just a plain login form. */
  loggedOutReason: string | null;
  loggedIn: (role: Role, username: string) => void;
  logOut: (api: ApiClient, reason?: string) => void;
  clearLoggedOutReason: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  role: null,
  username: null,
  loggedOutReason: null,
  loggedIn: (role, username) => set({ role, username, loggedOutReason: null }),
  logOut: (api, reason) => {
    api.token = null;
    api.role = null;
    void clearSession();
    set({ role: null, username: null, loggedOutReason: reason ?? null });
  },
  clearLoggedOutReason: () => set({ loggedOutReason: null }),
}));
