"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  type Wr3User,
  clearToken,
  fetchMe,
  fetchMyScans,
  getStoredToken,
  getWebApp,
  loginWithInitData,
  storeToken,
} from "@/lib/tg-session";
import { MiniAppScanForm } from "./scan-form";

type ScanRow = {
  id: string;
  address: string;
  network: string;
  stage: string;
  progress: number;
  score: number | null;
  tier: string | null;
  created_at: string;
};

type Phase = "loading" | "ready" | "no-tg" | "error";

export function MiniAppRoot() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<Wr3User | null>(null);
  const [scans, setScans] = useState<ScanRow[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      const tg = getWebApp();
      tg?.ready?.();
      tg?.expand?.();

      const initData = tg?.initData ?? "";
      let token = getStoredToken();

      if (!token && !initData) {
        if (!cancelled) setPhase("no-tg");
        return;
      }

      try {
        if (!token && initData) {
          const result = await loginWithInitData(initData);
          token = result.token;
          storeToken(token);
        }
        if (!token) throw new Error("no session token");

        const me = await fetchMe(token);
        if (cancelled) return;
        setUser(me);

        const myScans = await fetchMyScans(token);
        if (cancelled) return;
        setScans(myScans);
        setPhase("ready");
      } catch (e) {
        if (cancelled) return;
        clearToken();
        setError((e as Error).message);
        setPhase("error");
      }
    }

    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  if (phase === "loading") {
    return <p className="py-12 text-center text-zinc-500">Loading…</p>;
  }
  if (phase === "no-tg") {
    return (
      <div className="py-12 text-center">
        <h1 className="mb-2 text-xl font-bold">Open this from Telegram</h1>
        <p className="text-sm text-zinc-500">
          This page is a Telegram Mini App. Open it via the wr3 bot to sign in
          automatically.
        </p>
        <p className="mt-4">
          <Link href="/" className="text-sm underline">
            Use the web version →
          </Link>
        </p>
      </div>
    );
  }
  if (phase === "error") {
    return (
      <div className="py-12 text-center">
        <h1 className="mb-2 text-xl font-bold text-red-600">Auth error</h1>
        <p className="text-sm text-zinc-500">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-zinc-500">
          {user?.tier?.toUpperCase()} tier
        </p>
        <h1 className="text-2xl font-bold">
          {user?.display_name ?? user?.telegram_username ?? "wr3"}
        </h1>
      </header>

      <MiniAppScanForm />

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Your recent scans
        </h2>
        {scans.length === 0 ? (
          <p className="text-sm text-zinc-500">No scans yet. Start one above.</p>
        ) : (
          <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {scans.map((s) => (
              <li key={s.id}>
                <Link
                  href={`/tg/scan/${s.id}`}
                  className="flex items-center justify-between py-3 hover:bg-zinc-50 dark:hover:bg-zinc-900"
                >
                  <div className="min-w-0">
                    <p className="truncate font-mono text-sm">{s.address}</p>
                    <p className="text-xs text-zinc-500">
                      {s.network} · {s.stage} · {new Date(s.created_at).toLocaleString()}
                    </p>
                  </div>
                  <ScoreBadge score={s.score} tier={s.tier} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ScoreBadge({ score, tier }: { score: number | null; tier: string | null }) {
  if (score == null) {
    return <span className="text-xs text-zinc-400">running…</span>;
  }
  const color =
    tier === "red"
      ? "bg-red-600 text-white"
      : tier === "yellow"
        ? "bg-amber-500 text-white"
        : tier === "green"
          ? "bg-emerald-600 text-white"
          : "bg-blue-600 text-white";
  return (
    <span className={`ml-2 shrink-0 rounded px-2 py-1 text-xs font-semibold ${color}`}>
      {score.toFixed(0)}
    </span>
  );
}
