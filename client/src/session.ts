import { load } from "@tauri-apps/plugin-store";

import type { ApiClient } from "./api/client";
import type { Role } from "./types";

const STORE_FILE = "session.json";

export interface PersistedSession {
  token: string;
  role: Role;
  username: string;
}

export async function saveSession(session: PersistedSession): Promise<void> {
  const store = await load(STORE_FILE);
  await store.set("session", session);
  await store.save();
}

export async function loadSession(): Promise<PersistedSession | null> {
  const store = await load(STORE_FILE);
  const session = await store.get<PersistedSession>("session");
  return session ?? null;
}

export async function clearSession(): Promise<void> {
  const store = await load(STORE_FILE);
  await store.delete("session");
  await store.save();
}

/** Rehydrates the ApiClient's in-memory token from persisted storage on
 * app startup, so the cashier doesn't have to log in again every launch. */
export async function restoreSession(api: ApiClient): Promise<PersistedSession | null> {
  const session = await loadSession();
  if (session) {
    api.token = session.token;
    api.role = session.role;
  }
  return session;
}
