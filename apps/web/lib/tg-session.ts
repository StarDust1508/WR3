/**
 * Telegram Mini App auth helpers.
 *
 * Lifecycle:
 *   1. On Mini App mount, read window.Telegram.WebApp.initData
 *   2. POST it to /api/v1/auth/tg/login → JWT
 *   3. Store JWT in sessionStorage (not localStorage — Mini App is per-session)
 *   4. Use Authorization: Bearer <jwt> for subsequent API calls
 */

const STORAGE_KEY = "wr3.tg.token";

type TgWebApp = {
  ready?: () => void;
  expand?: () => void;
  initData?: string;
  initDataUnsafe?: { user?: { id: number; first_name?: string; username?: string } };
  themeParams?: Record<string, string>;
};

declare global {
  interface Window {
    Telegram?: { WebApp?: TgWebApp };
  }
}

export type Wr3User = {
  id: string;
  telegram_user_id: number | null;
  telegram_username: string | null;
  display_name: string | null;
  tier: string;
};

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function storeToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, token);
  } catch {
    /* ignore */
  }
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export function getWebApp(): TgWebApp | null {
  if (typeof window === "undefined") return null;
  return window.Telegram?.WebApp ?? null;
}

export async function loginWithInitData(initData: string): Promise<{
  token: string;
  user: Wr3User;
}> {
  const res = await fetch("/api/v1/auth/tg/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ init_data: initData }),
  });
  if (!res.ok) {
    throw new Error(`tg login failed (${res.status})`);
  }
  return res.json();
}

export async function fetchMe(token: string): Promise<Wr3User> {
  const res = await fetch("/api/v1/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("not authenticated");
  return res.json();
}

export async function fetchMyScans(token: string): Promise<Array<{
  id: string;
  address: string;
  network: string;
  stage: string;
  progress: number;
  score: number | null;
  tier: string | null;
  created_at: string;
}>> {
  const res = await fetch("/api/v1/scan/me?limit=50", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("failed to load scans");
  return res.json();
}
