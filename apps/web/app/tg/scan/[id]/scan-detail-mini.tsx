"use client";

import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Info,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
} from "lucide-react";
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

        // Poll while pipeline is running.
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
    return (
      <main className="mx-auto max-w-xl px-4 pb-12 pt-4">
        <BackLink />
        <div className="mt-8 flex flex-col items-center gap-2 text-center">
          <ShieldOff size={28} color="var(--tg-destructive)" />
          <p className="text-sm" style={{ color: "var(--tg-destructive)" }}>
            {error}
          </p>
        </div>
      </main>
    );
  }
  if (!scan) {
    return (
      <main className="mx-auto max-w-xl px-4 pb-12 pt-4">
        <BackLink />
        <div
          className="flex items-center justify-center gap-2 py-16"
          style={{ color: "var(--tg-hint)" }}
        >
          <Loader2 className="animate-spin" size={16} />
          <span className="text-sm">Loading…</span>
        </div>
      </main>
    );
  }

  const active = scan.findings.filter((f) => !f.dismissed);
  const counts = countBySeverity(active);

  return (
    <main className="mx-auto max-w-xl px-4 pb-32 pt-4">
      <BackLink />

      <header className="mb-4 mt-2">
        <p className="tg-hint mb-1">{scan.network.toUpperCase()}</p>
        <p className="break-all font-mono text-sm" style={{ color: "var(--tg-text)" }}>
          {scan.address}
        </p>
      </header>

      {scan.stage !== "done" ? (
        <ProgressCard stage={scan.stage} progress={scan.progress} />
      ) : (
        <ScoreCard
          score={scan.score ?? 0}
          tier={scan.tier ?? "yellow"}
          counts={counts}
          duration={scan.duration_seconds}
        />
      )}

      {active.length > 0 && (
        <section className="mt-6">
          <h2 className="tg-hint mb-2">Findings · {active.length}</h2>
          <ul className="flex flex-col gap-2">
            {active.map((f) => (
              <FindingRow key={f.id} finding={f} />
            ))}
          </ul>
        </section>
      )}

      <p
        className="mt-10 text-center text-[11px] leading-relaxed"
        style={{ color: "var(--tg-hint)" }}
      >
        AI-assisted audit. Best-effort, no warranty.
      </p>
    </main>
  );
}

function BackLink() {
  return (
    <Link
      href="/tg"
      className="inline-flex items-center gap-1 text-sm"
      style={{ color: "var(--tg-hint)" }}
    >
      <ArrowLeft size={14} />
      Back
    </Link>
  );
}

function ProgressCard({ stage, progress }: { stage: string; progress: number }) {
  return (
    <div className="tg-card">
      <p className="tg-hint mb-2">In progress</p>
      <div
        className="mb-2 flex items-center gap-2 text-sm"
        style={{ color: "var(--tg-text)" }}
      >
        <Loader2 className="animate-spin" size={14} />
        {stageLabel(stage)}{" "}
        <span style={{ color: "var(--tg-hint)" }}>· {progress}%</span>
      </div>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full"
        style={{ background: "color-mix(in srgb, var(--tg-text) 10%, transparent)" }}
      >
        <div
          style={{
            width: `${Math.min(100, Math.max(0, progress))}%`,
            height: "100%",
            background: "var(--tg-button)",
            transition: "width 400ms ease",
          }}
        />
      </div>
    </div>
  );
}

function ScoreCard({
  score,
  tier,
  counts,
  duration,
}: {
  score: number;
  tier: string;
  counts: SeverityCounts;
  duration: number | null;
}) {
  const tierClass = `tier-${tier}`;
  const verdict = verdictFor(tier);
  return (
    <div className="tg-card flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <div className={tierClass} style={{ minWidth: 88, textAlign: "center" }}>
          <p style={{ fontSize: 44, lineHeight: 1, fontWeight: 800 }}>
            {Math.round(score)}
          </p>
          <p
            style={{
              fontSize: 11,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              fontWeight: 700,
            }}
          >
            /100
          </p>
        </div>
        <div className="min-w-0 flex-1">
          <p style={{ fontWeight: 700, color: "var(--tg-text)" }}>
            {verdict.label}
          </p>
          <p className="text-sm" style={{ color: "var(--tg-hint)" }}>
            {verdict.body}
            {duration != null && ` · ${duration.toFixed(1)}s`}
          </p>
        </div>
      </div>
      <SeveritySummary counts={counts} />
    </div>
  );
}

function SeveritySummary({ counts }: { counts: SeverityCounts }) {
  const order: Array<{ key: keyof SeverityCounts; cls: string; label: string }> = [
    { key: "critical", cls: "sev-chip-critical", label: "Critical" },
    { key: "high", cls: "sev-chip-high", label: "High" },
    { key: "medium", cls: "sev-chip-medium", label: "Med" },
    { key: "low", cls: "sev-chip-low", label: "Low" },
    { key: "info", cls: "sev-chip-info", label: "Info" },
  ];
  const visible = order.filter((o) => counts[o.key] > 0);
  if (visible.length === 0) {
    return (
      <p
        className="flex items-center gap-1 text-sm"
        style={{ color: "var(--sev-good)" }}
      >
        <CheckCircle2 size={14} /> No active findings.
      </p>
    );
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {visible.map((o) => (
        <span key={o.key} className={`tg-chip ${o.cls}`}>
          {counts[o.key]} {o.label}
        </span>
      ))}
    </div>
  );
}

function FindingRow({ finding }: { finding: Finding }) {
  const sev = finding.severity.toLowerCase();
  const sevClass =
    sev === "critical"
      ? "sev-chip-critical"
      : sev === "high"
        ? "sev-chip-high"
        : sev === "medium"
          ? "sev-chip-medium"
          : sev === "low"
            ? "sev-chip-low"
            : "sev-chip-info";

  const Icon =
    sev === "critical" || sev === "high"
      ? ShieldAlert
      : sev === "medium"
        ? AlertTriangle
        : sev === "low"
          ? ShieldCheck
          : Info;

  const iconColor =
    sev === "critical"
      ? "var(--sev-critical)"
      : sev === "high"
        ? "var(--sev-high)"
        : sev === "medium"
          ? "var(--sev-medium)"
          : sev === "low"
            ? "var(--sev-low)"
            : "var(--sev-info)";

  return (
    <li className="tg-card">
      <div className="flex items-start gap-3">
        <Icon
          size={18}
          color={iconColor}
          style={{ flexShrink: 0, marginTop: 2 }}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`tg-chip ${sevClass}`}>{sev.toUpperCase()}</span>
            {finding.poc_validated && (
              <span className="tg-chip sev-chip-good">PoC ✓</span>
            )}
            {finding.line != null && (
              <span className="font-mono text-xs" style={{ color: "var(--tg-hint)" }}>
                L{finding.line}
              </span>
            )}
          </div>
          <p
            className="mt-1 text-sm font-medium leading-snug"
            style={{ color: "var(--tg-text)" }}
          >
            {finding.title}
          </p>
          {finding.description && (
            <p className="mt-1 text-xs leading-relaxed" style={{ color: "var(--tg-hint)" }}>
              {finding.description}
            </p>
          )}
        </div>
      </div>
    </li>
  );
}

type SeverityCounts = {
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
};

function countBySeverity(findings: Finding[]): SeverityCounts {
  const c: SeverityCounts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  for (const f of findings) {
    const sev = f.severity.toLowerCase() as keyof SeverityCounts;
    if (sev in c) c[sev] += 1;
  }
  return c;
}

function stageLabel(stage: string): string {
  return (
    {
      queued: "Preparing",
      static: "Static analysis",
      triage: "AI triage",
      poc: "Generating PoCs",
      fuzzing: "AI fuzzing",
      scoring: "Scoring",
    }[stage] ?? stage
  );
}

function verdictFor(tier: string): { label: string; body: string } {
  return (
    {
      red: { label: "High risk", body: "Critical or high-severity finding present." },
      yellow: { label: "Caution", body: "Medium-severity findings — review recommended." },
      green: { label: "Acceptable", body: "Only minor issues detected." },
      blue: { label: "Excellent", body: "No security findings of note." },
    }[tier] ?? { label: tier, body: "" }
  );
}
