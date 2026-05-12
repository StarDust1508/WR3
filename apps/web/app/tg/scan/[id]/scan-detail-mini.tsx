"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getStoredToken } from "@/lib/tg-session";

type Finding = {
  id: string;
  title: string;
  description: string;
  severity: string;
  source_engine: string;
  line: number | null;
  dismissed: boolean;
  poc_validated?: boolean;
};

type ScanDetail = {
  id: string;
  address: string;
  network: string;
  stage: string;
  progress: number;
  score: number | null;
  tier: string | null;
  duration_seconds: number | null;
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
        if (data.stage !== "done" && data.stage !== "error") {
          timer = setTimeout(load, 1500);
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    }
    load();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [scanId]);

  if (error) {
    return (
      <main className="mx-auto max-w-xl px-4 pb-12 pt-4">
        <BackLink />
        <p className="mt-6 text-sm" style={{ color: "var(--hb-error)" }}>
          <span>ERR </span>{error}
        </p>
      </main>
    );
  }
  if (!scan) {
    return (
      <main className="mx-auto max-w-xl px-4 pb-12 pt-4">
        <BackLink />
        <p className="mt-12 text-center text-xs hb-prompt">
          loading<span className="hb-cursor" />
        </p>
      </main>
    );
  }

  const active = scan.findings.filter((f) => !f.dismissed);
  const counts = countBySeverity(active);

  return (
    <main className="mx-auto max-w-xl px-4 pb-32 pt-4">
      <BackLink />

      <header className="mb-4 mt-3">
        <p className="text-[10px]" style={{ color: "var(--hb-text-muted)" }}>
          // {scan.network} target
        </p>
        <p
          className="break-all text-xs"
          style={{ color: "var(--hb-text-hi)" }}
        >
          {scan.address}
        </p>
      </header>

      {scan.stage !== "done"
        ? <ProgressCard stage={scan.stage} progress={scan.progress} />
        : <ScoreCard score={scan.score ?? 0} tier={scan.tier ?? "yellow"} counts={counts} duration={scan.duration_seconds} />}

      {active.length > 0 && (
        <section className="mt-5">
          <h2 className="tg-hint mb-2">findings · {active.length}</h2>
          <ul className="flex flex-col gap-1.5">
            {active.map((f) => <FindingRow key={f.id} finding={f} />)}
          </ul>
        </section>
      )}

      <p className="mt-10 text-center text-[10px]" style={{ color: "var(--hb-text-muted)" }}>
        ai-assisted audit · best-effort, no warranty
      </p>
    </main>
  );
}

function BackLink() {
  return (
    <Link href="/tg" className="text-xs" style={{ color: "var(--hb-text-dim)" }}>
      ← back
    </Link>
  );
}

function ProgressCard({ stage, progress }: { stage: string; progress: number }) {
  return (
    <div className="tg-card">
      <p className="tg-hint mb-2">in progress</p>
      <p className="mb-2 text-xs" style={{ color: "var(--hb-text-hi)" }}>
        <span className="hb-cursor">{stageLabel(stage)}</span>
        <span className="ml-2" style={{ color: "var(--hb-text-muted)" }}>{progress}%</span>
      </p>
      <div className="h-1 w-full overflow-hidden" style={{ background: "var(--hb-bg)", border: "1px solid var(--hb-border)" }}>
        <div
          style={{
            width: `${Math.min(100, Math.max(0, progress))}%`,
            height: "100%",
            background: "var(--hb-primary)",
            transition: "width 400ms ease",
          }}
        />
      </div>
    </div>
  );
}

function ScoreCard({ score, tier, counts, duration }: { score: number; tier: string; counts: SeverityCounts; duration: number | null }) {
  const tierClass = `tier-${tier}`;
  const verdict = verdictFor(tier);
  return (
    <div className="tg-card flex flex-col gap-3">
      <div className="flex items-baseline gap-3">
        <span className={`${tierClass}`} style={{ fontSize: 36, fontWeight: 800, lineHeight: 1 }}>
          {Math.round(score)}
        </span>
        <span style={{ color: "var(--hb-text-muted)", fontSize: 11 }}>/100</span>
        <span className="ml-auto text-[10px]" style={{ color: "var(--hb-text-muted)" }}>
          {duration != null && `${duration.toFixed(1)}s`}
        </span>
      </div>
      <p className="text-xs" style={{ color: "var(--hb-text-hi)" }}>
        <span className={tierClass}>[{tier}]</span> {verdict.label}
      </p>
      <p className="text-[11px]" style={{ color: "var(--hb-text-dim)" }}>{verdict.body}</p>
      <SeveritySummary counts={counts} />
    </div>
  );
}

function SeveritySummary({ counts }: { counts: SeverityCounts }) {
  const order: Array<{ k: keyof SeverityCounts; cls: string; label: string }> = [
    { k: "critical", cls: "sev-chip-critical", label: "crit" },
    { k: "high",     cls: "sev-chip-high",     label: "high" },
    { k: "medium",   cls: "sev-chip-medium",   label: "med" },
    { k: "low",      cls: "sev-chip-low",      label: "low" },
    { k: "info",     cls: "sev-chip-info",     label: "info" },
  ];
  const visible = order.filter((o) => counts[o.k] > 0);
  if (visible.length === 0) {
    return <p className="text-xs" style={{ color: "var(--sev-good)" }}>✓ clean</p>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {visible.map((o) => (
        <span key={o.k} className={`tg-chip ${o.cls}`}>
          {counts[o.k]} {o.label}
        </span>
      ))}
    </div>
  );
}

function FindingRow({ finding }: { finding: Finding }) {
  const sev = finding.severity.toLowerCase();
  const sevClass =
    sev === "critical" ? "sev-chip-critical"
    : sev === "high"   ? "sev-chip-high"
    : sev === "medium" ? "sev-chip-medium"
    : sev === "low"    ? "sev-chip-low"
                       : "sev-chip-info";

  return (
    <li className="tg-card" style={{ padding: 12 }}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`tg-chip ${sevClass}`}>{sev}</span>
        {finding.poc_validated && (
          <span className="tg-chip sev-chip-good">poc ok</span>
        )}
        <span className="text-[10px]" style={{ color: "var(--hb-text-muted)" }}>
          {finding.source_engine}{finding.line != null && `:${finding.line}`}
        </span>
      </div>
      <p className="mt-2 text-xs font-medium leading-snug" style={{ color: "var(--hb-text-hi)" }}>
        {finding.title}
      </p>
      {finding.description && (
        <p className="mt-1 text-[11px] leading-relaxed" style={{ color: "var(--hb-text-dim)" }}>
          {finding.description}
        </p>
      )}
    </li>
  );
}

type SeverityCounts = { critical: number; high: number; medium: number; low: number; info: number };

function countBySeverity(findings: Finding[]): SeverityCounts {
  const c: SeverityCounts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  for (const f of findings) {
    const k = f.severity.toLowerCase() as keyof SeverityCounts;
    if (k in c) c[k] += 1;
  }
  return c;
}

function stageLabel(stage: string): string {
  return ({
    queued: "preparing",
    static: "static-analysis",
    triage: "ai-triage",
    poc: "poc-generation",
    fuzzing: "ai-fuzzing",
    scoring: "scoring",
  } as Record<string, string>)[stage] ?? stage;
}

function verdictFor(tier: string): { label: string; body: string } {
  return ({
    red:    { label: "high risk",     body: "critical or high-severity finding present" },
    yellow: { label: "caution",       body: "medium-severity findings — review recommended" },
    green:  { label: "acceptable",    body: "only minor issues detected" },
    blue:   { label: "excellent",     body: "no security findings of note" },
  } as Record<string, { label: string; body: string }>)[tier] ?? { label: tier, body: "" };
}
