import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { ApiClient } from "./api/client";
import { config } from "./config";
import { restoreSession } from "./session";
import { useSessionStore } from "./stores/sessionStore";

interface AppServices {
  api: ApiClient;
}

export const AppServicesContext = createContext<AppServices | null>(null);

/** Creates the ApiClient and rehydrates a persisted JWT session
 * (`plugin-store`) so the cashier isn't forced to log in on every launch.
 * Renders nothing until the session check settles — every screen below can
 * assume `useAppServices()` is non-null. Every read and write goes straight
 * to the server; there is no local cache. */
export function AppServicesProvider({ children }: { children: ReactNode }) {
  const [services, setServices] = useState<AppServices | null>(null);
  const loggedIn = useSessionStore((s) => s.loggedIn);

  useEffect(() => {
    const api = new ApiClient(config.apiBaseUrl);
    api.onUnauthorized = () => {
      useSessionStore.getState().logOut(api, "Your session is no longer valid — please log in again.");
    };
    let cancelled = false;

    restoreSession(api)
      .catch((err) => {
        // plugin-store's Tauri IPC is only present inside the real Tauri
        // webview — e.g. running this in a plain browser tab for UI
        // debugging, or a corrupted/missing store file, would otherwise
        // throw here and leave the app permanently on a blank screen with
        // `services` never set. Fail back to "no persisted session"
        // instead — the cashier just sees the login screen.
        console.error("restoreSession failed, continuing without a persisted session", err);
        return null;
      })
      .then((session) => {
        if (cancelled) return;
        setServices({ api });
        if (session) loggedIn(session.role, session.username);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!services) return null; // brief splash while the session check settles
  return <AppServicesContext.Provider value={services}>{children}</AppServicesContext.Provider>;
}

export function useAppServices(): AppServices {
  const ctx = useContext(AppServicesContext);
  if (!ctx) throw new Error("useAppServices must be used within AppServicesProvider");
  return ctx;
}
