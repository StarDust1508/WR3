/**
 * Owner preferences API client.
 *
 * Toggles map 1:1 to `users.preferences` JSONB on the server. Each toggle
 * actually changes pipeline behaviour — they are NOT cosmetic.
 */

import { getStoredToken } from "./tg-session";

export type Prefs = {
  auto_poc: boolean;
  auto_fuzzing: boolean;
  multi_agent_triage: boolean;
  continuous_monitoring: boolean;
  anonymous_in_public: boolean;
};

export const PREFS_DEFAULT: Prefs = {
  auto_poc: true,
  auto_fuzzing: true,
  multi_agent_triage: true,
  continuous_monitoring: false,
  anonymous_in_public: false,
};

export async function fetchPrefs(): Promise<Prefs> {
  const token = getStoredToken();
  const res = await fetch("/api/v1/auth/preferences", {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`fetch prefs failed (${res.status})`);
  return { ...PREFS_DEFAULT, ...(await res.json()) };
}

export async function patchPrefs(patch: Partial<Prefs>): Promise<Prefs> {
  const token = getStoredToken();
  const res = await fetch("/api/v1/auth/preferences", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(`patch prefs failed (${res.status})`);
  return { ...PREFS_DEFAULT, ...(await res.json()) };
}
