"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getStoredToken } from "@/lib/tg-session";

type SimilarIncident = {
  incident_id: string;
  title: string;
  url: string;
  source: string;
  loss_usd: number | null;
  published_at: string;
  similarity: number;
};

type Finding = {
  id: string;
  title: string;
  description: string;
  severity: string;
  source_engine: string;
  line: number | null;
  dismissed: boolean;
  poc_validated?: boolean;
  metadata?: { similar_incidents?: SimilarIncident[] } | null;
};

type ChainMetadata = {
  executable?: boolean;
  loader?: string | null;
  upgradeable?: boolean;
  upgrade_authority?: string | null;
  last_upgrade_slot?: number | null;
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
  report?: {
    chain_metadata?: ChainMetadata;
  } | null;
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
        <p
          className="mt-6 text-sm leading-relaxed"
          style={{
            color: "var(--hb-error)",
            background: "rgba(248,113,113,0.08)",
            border: "1px solid rgba(248,113,113,0.30)",
            padding: "10px 12px",
            borderRadius: 4,
          }}
        >
          {error}
        </p>
      </main>
    );
  }
  if (!scan) {
    return (
      <main className="mx-auto max-w-xl px-4 pb-12 pt-4">
        <BackLink />
        <p
          className="mt-12 text-center text-xs hb-dots"
          style={{ color: "var(--hb-text-dim)" }}
        >
          Загрузка
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
        <p
          className="text-[10px] uppercase"
          style={{ color: "var(--hb-text-dim)", letterSpacing: "0.08em" }}
        >
          Контракт · {scan.network}
        </p>
        <p
          className="mt-1 break-all text-xs font-medium"
          style={{ color: "var(--hb-text-hi)" }}
        >
          {scan.address}
        </p>
      </header>

      {scan.stage !== "done"
        ? <ProgressCard stage={scan.stage} progress={scan.progress} />
        : <ScoreCard score={scan.score ?? 0} tier={scan.tier ?? "yellow"} counts={counts} duration={scan.duration_seconds} />}

      {scan.report?.chain_metadata?.executable !== undefined && (
        <SolanaMetaCard meta={scan.report.chain_metadata} />
      )}

      {scan.stage === "done" && (
        <p className="mt-3 text-center text-[11px]">
          <a
            href={`/api/v1/scan/${scan.id}/report.md`}
            style={{
              color: "var(--hb-primary)",
              textDecoration: "underline",
              textUnderlineOffset: 3,
            }}
            download
          >
            Скачать отчёт в Markdown
          </a>
        </p>
      )}

      {active.length > 0 && (
        <section className="mt-5">
          <h2 className="tg-hint mb-2">Находки · {active.length}</h2>
          <ul className="flex flex-col gap-1.5">
            {active.map((f) => <FindingRow key={f.id} finding={f} />)}
          </ul>
        </section>
      )}

      <p
        className="mt-10 text-center text-[10px] leading-relaxed"
        style={{ color: "var(--hb-text-dim)" }}
      >
        AI-аудит — best-effort. Для критичных контрактов рекомендуем ручное ревью.
      </p>
    </main>
  );
}

function SolanaMetaCard({ meta }: { meta: ChainMetadata }) {
  return (
    <div className="tg-card mt-3" style={{ padding: 14 }}>
      <p className="tg-hint mb-2">On-chain метаданные</p>
      <dl
        className="grid gap-y-1.5 text-[11px]"
        style={{
          gridTemplateColumns: "max-content 1fr",
          columnGap: 12,
          color: "var(--hb-text-dim)",
        }}
      >
        <dt>Исполняемая</dt>
        <dd style={{ color: "var(--hb-text-hi)" }}>{meta.executable ? "Да" : "Нет"}</dd>

        <dt>Обновляемая</dt>
        <dd>
          {meta.upgradeable ? (
            <span style={{ color: "var(--hb-warn, #f59e0b)", fontWeight: 600 }}>
              Да — риск централизации
            </span>
          ) : (
            <span style={{ color: "var(--hb-text-hi)" }}>Нет — байткод заморожен</span>
          )}
        </dd>

        {meta.upgradeable && meta.upgrade_authority && (
          <>
            <dt>Upgrade authority</dt>
            <dd
              className="break-all"
              style={{
                color: "var(--hb-text-hi)",
                fontFamily: "monospace",
                fontSize: 10,
              }}
            >
              {meta.upgrade_authority}
            </dd>
          </>
        )}
        {meta.upgradeable && meta.last_upgrade_slot != null && (
          <>
            <dt>Last upgrade slot</dt>
            <dd
              style={{ color: "var(--hb-text-hi)", fontFamily: "monospace" }}
            >
              {meta.last_upgrade_slot.toLocaleString("ru-RU")}
            </dd>
          </>
        )}
      </dl>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/tg"
      className="text-xs"
      style={{
        color: "var(--hb-text-dim)",
        textDecoration: "none",
      }}
    >
      ‹ Назад
    </Link>
  );
}

function ProgressCard({ stage, progress }: { stage: string; progress: number }) {
  return (
    <div className="tg-card">
      <p className="tg-hint mb-2">Выполняется</p>
      <p className="mb-2 flex items-baseline justify-between text-xs">
        <span style={{ color: "var(--hb-text-hi)" }}>{stageLabel(stage)}</span>
        <span style={{ color: "var(--hb-text-dim)" }}>{progress}%</span>
      </p>
      <div
        className="h-1 w-full overflow-hidden"
        style={{ background: "var(--hb-bg)", border: "1px solid var(--hb-border)" }}
      >
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
    <div className="tg-card flex flex-col gap-3">
      <div className="flex items-baseline gap-3">
        <span
          className={tierClass}
          style={{ fontSize: 44, fontWeight: 800, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}
        >
          {Math.round(score)}
        </span>
        <span style={{ color: "var(--hb-text-dim)", fontSize: 12 }}>/ 100</span>
        <span
          className="ml-auto text-[10px]"
          style={{ color: "var(--hb-text-dim)" }}
        >
          {duration != null && `${duration.toFixed(1)} с`}
        </span>
      </div>
      {/* Score bar — turns the number into context. */}
      <div
        aria-hidden="true"
        style={{
          height: 4,
          background: "var(--hb-bg)",
          border: "1px solid var(--hb-border)",
          borderRadius: 2,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.min(100, Math.max(0, score))}%`,
            height: "100%",
            background: "currentColor",
          }}
          className={tierClass}
        />
      </div>
      <p className="text-xs font-semibold" style={{ color: "var(--hb-text-hi)" }}>
        {verdict.label}
      </p>
      <p className="text-[11px] leading-relaxed" style={{ color: "var(--hb-text-dim)" }}>
        {verdict.body}
      </p>
      <SeveritySummary counts={counts} />
    </div>
  );
}

function SeveritySummary({ counts }: { counts: SeverityCounts }) {
  const order: Array<{ k: keyof SeverityCounts; cls: string; label: string }> = [
    { k: "critical", cls: "sev-chip-critical", label: "Critical" },
    { k: "high",     cls: "sev-chip-high",     label: "High" },
    { k: "medium",   cls: "sev-chip-medium",   label: "Medium" },
    { k: "low",      cls: "sev-chip-low",      label: "Low" },
    { k: "info",     cls: "sev-chip-info",     label: "Info" },
  ];
  const visible = order.filter((o) => counts[o.k] > 0);
  if (visible.length === 0) {
    return (
      <p
        className="text-xs font-medium"
        style={{ color: "var(--sev-good, #4ade80)" }}
      >
        Уязвимостей не найдено
      </p>
    );
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
  const similar = finding.metadata?.similar_incidents ?? [];

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
      {similar.length > 0 && <SimilarIncidents incidents={similar} />}
    </li>
  );
}

function SimilarIncidents({ incidents }: { incidents: SimilarIncident[] }) {
  return (
    <div
      className="mt-2 border-t pt-2"
      style={{ borderColor: "var(--hb-border)" }}
    >
      <p
        className="text-[10px] uppercase"
        style={{ color: "var(--hb-text-dim)", letterSpacing: "0.08em" }}
      >
        Похожие реальные эксплойты
      </p>
      <ul className="mt-1 flex flex-col gap-1">
        {incidents.map((i) => (
          <li key={i.incident_id}>
            <a
              href={i.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px]"
              style={{
                color: "var(--hb-primary)",
                textDecoration: "none",
                lineHeight: 1.4,
                display: "block",
              }}
            >
              <span style={{ color: "var(--hb-text-muted)", marginRight: 6 }}>
                {Math.round(i.similarity * 100)}%
              </span>
              {i.title}
              {i.loss_usd != null && (
                <span style={{ color: "#f87171", marginLeft: 6 }}>
                  ${formatLoss(i.loss_usd)}
                </span>
              )}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatLoss(usd: number): string {
  if (usd >= 1_000_000_000) return `${(usd / 1_000_000_000).toFixed(1)}B`;
  if (usd >= 1_000_000) return `${(usd / 1_000_000).toFixed(1)}M`;
  if (usd >= 1_000) return `${(usd / 1_000).toFixed(0)}K`;
  return usd.toString();
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
  return (
    {
      queued: "Подготовка",
      static: "Статический анализ",
      triage: "LLM-триаж",
      poc: "Проверка эксплойтов (PoC)",
      fuzzing: "AI-fuzzing",
      scoring: "Оценка",
    } as Record<string, string>
  )[stage] ?? stage;
}

function verdictFor(tier: string): { label: string; body: string } {
  return (
    {
      red: {
        label: "Высокий риск",
        body: "Есть critical или high-severity находки. Перед деплоем требуется ревью.",
      },
      yellow: {
        label: "Осторожно",
        body: "Найдены medium-severity замечания. Стоит просмотреть перед продакшеном.",
      },
      green: {
        label: "Приемлемо",
        body: "Только минорные замечания. Существенных security-проблем не выявлено.",
      },
      blue: {
        label: "Отлично",
        body: "Значимых security-находок нет. Контракт прошёл все стадии чисто.",
      },
    } as Record<string, { label: string; body: string }>
  )[tier] ?? { label: tier, body: "" };
}
