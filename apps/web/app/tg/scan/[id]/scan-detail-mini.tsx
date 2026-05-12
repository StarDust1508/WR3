"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getStoredToken } from "@/lib/tg-session";

type Finding = {
  id: string;
  title: string;
  severity: string;
  source_engine: string;
  line: number | null;
  dismissed: boolean;
};

type ScanDetail = {
  id: string;
  address: string;
  network: string;
  stage: string;
  progress: number;
  score: number | null;
  tier: string | null;
  findings: Finding[];
};

export function ScanDetailMini({ scanId }: { scanId: string }) {
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function load() {
      try {
        const token = getStoredToken();
        const headers: Record<string, string> = {};
        if (token) headers.Authorization = `Bearer ${token}`;
        const res = await fetch(`/api/v1/scan/${scanId}`, { headers });
        if (!res.ok) throw new Error(`load failed (${res.status})`);
        const data = (await res.json()) as ScanDetail;
        if (cancelled) return;
        setScan(data);

        // Poll until done; SSE works in Mini App but fetch+poll is simpler/safer.
        if (data.stage !== "done" && data.stage !== "error") {
          timer = setTimeout(load, 1500);
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    }

    load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [scanId]);

  if (error) {
    return <p className="py-12 text-center text-sm text-red-600">{error}</p>;
  }
  if (!scan) {
    return <p className="py-12 text-center text-sm text-zinc-500">Loading…</p>;
  }

  const active = scan.findings.filter((f) => !f.dismissed);

  return (
    <div className="space-y-4">
      <Link href="/tg" className="text-sm text-zinc-500">
        ← Back
      </Link>

      <header>
        <p className="font-mono text-sm">{scan.address}</p>
        <p className="text-xs text-zinc-500">{scan.network}</p>
      </header>

      {scan.stage !== "done" ? (
        <div>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {scan.stage} · {scan.progress}%
          </p>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
            <div
              className="h-full bg-zinc-900 transition-all dark:bg-zinc-50"
              style={{ width: `${scan.progress}%` }}
            />
          </div>
        </div>
      ) : (
        <ScoreCard score={scan.score ?? 0} tier={scan.tier ?? "yellow"} />
      )}

      {active.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Findings ({active.length})
          </h2>
          <ul className="space-y-1">
            {active.map((f) => (
              <li
                key={f.id}
                className="rounded-md border border-zinc-200 px-3 py-2 dark:border-zinc-800"
              >
                <div className="flex items-center gap-2">
                  <SeverityChip s={f.severity} />
                  <p className="flex-1 truncate text-sm">{f.title}</p>
                  {f.line != null && (
                    <span className="font-mono text-xs text-zinc-500">L{f.line}</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function ScoreCard({ score, tier }: { score: number; tier: string }) {
  const color =
    tier === "red"
      ? "text-red-600"
      : tier === "yellow"
        ? "text-amber-500"
        : tier === "green"
          ? "text-emerald-600"
          : "text-blue-600";
  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <p className="text-xs uppercase tracking-wide text-zinc-500">Score</p>
      <p className={`text-5xl font-bold ${color}`}>{score.toFixed(0)}</p>
      <p className={`text-sm ${color}`}>{tier}</p>
    </div>
  );
}

function SeverityChip({ s }: { s: string }) {
  const map: Record<string, string> = {
    critical: "bg-red-600 text-white",
    high: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
    medium: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
    low: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
    info: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  };
  return (
    <span
      className={`shrink-0 rounded px-2 py-0.5 text-xs font-semibold ${map[s] ?? map.info}`}
    >
      {s.toUpperCase()}
    </span>
  );
}
