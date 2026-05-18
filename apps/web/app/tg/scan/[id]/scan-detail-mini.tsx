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
          className="tg-glass tg-animate-in mt-6 text-sm leading-relaxed"
          style={{
            color: "var(--hb-error)",
            borderColor: "rgba(248,113,113,0.30)",
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

      <header className="tg-animate-in tg-delay-1 mb-4 mt-3">
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

      <div className="tg-animate-in tg-delay-2">
        {scan.stage !== "done"
          ? <ProgressCard stage={scan.stage} progress={scan.progress} />
          : <ScoreCard score={scan.score ?? 0} tier={scan.tier ?? "yellow"} counts={counts} duration={scan.duration_seconds} />}
      </div>

      {scan.report?.chain_metadata?.executable !== undefined && (
        <div className="tg-animate-in tg-delay-3">
          <SolanaMetaCard meta={scan.report.chain_metadata} />
        </div>
      )}

      {scan.stage === "done" && (
        <p className="tg-animate-in tg-delay-4 mt-3 text-center text-[11px]">
          <a
            href={`/api/v1/scan/${scan.id}/report.md`}
            className="tg-underline-anim"
            style={{
              color: "var(--hb-primary)",
            }}
            download
          >
            Скачать отчёт в Markdown
          </a>
        </p>
      )}

      {active.length > 0 && (
        <section className="tg-animate-in tg-delay-5 mt-5">
          <h2 className="tg-hint mb-2">Находки · {active.length}</h2>
          <ul className="flex flex-col gap-2">
            {active.map((f, i) => (
              <FindingRow
                key={f.id}
                finding={f}
                delayIndex={i}
              />
            ))}
          </ul>
        </section>
      )}

      <p
        className="tg-animate-in tg-delay-7 mt-10 text-center text-[10px] leading-relaxed"
        style={{ color: "var(--hb-text-dim)" }}
      >
        AI-аудит — best-effort. Для критичных контрактов рекомендуем ручное ревью.
      </p>
    </main>
  );
}

function SolanaMetaCard({ meta }: { meta: ChainMetadata }) {
  return (
    <div className="tg-glass tg-glow mt-3" style={{ padding: 14 }}>
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
      className="inline-flex items-center gap-1 text-xs"
      style={{
        color: "var(--hb-text-dim)",
        textDecoration: "none",
        transition: "color 0.2s ease",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.color = "var(--hb-primary)")}
      onMouseLeave={(e) => (e.currentTarget.style.color = "var(--hb-text-dim)")}
    >
      <span style={{ fontSize: 16, lineHeight: 1, transition: "transform 0.2s ease" }}>‹</span>
      {" "}Назад
    </Link>
  );
}

function ProgressCard({ stage, progress }: { stage: string; progress: number }) {
  const pct = Math.min(100, Math.max(0, progress));
  return (
    <div className="tg-glass tg-glow">
      <p className="tg-hint mb-3">Выполняется</p>
      <div className="mb-3 flex items-center justify-between">
        <span
          className="text-xs font-semibold"
          style={{ color: "var(--hb-text-hi)" }}
        >
          {stageLabel(stage)}
        </span>
        <span
          style={{
            color: "var(--hb-primary)",
            fontSize: 13,
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 36,
            height: 36,
            borderRadius: "50%",
            border: "2px solid rgba(74, 222, 128, 0.3)",
            animation: "pulse-ring 2s ease-in-out infinite",
          }}
        >
          {pct}%
        </span>
      </div>
      <div
        style={{
          height: 4,
          background: "rgba(74, 222, 128, 0.08)",
          borderRadius: 2,
          overflow: "hidden",
          position: "relative",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: "linear-gradient(90deg, var(--hb-primary), #86efac)",
            borderRadius: 2,
            transition: "width 400ms ease",
            animation: "progress-glow 2s ease-in-out infinite",
            position: "relative",
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
  const tierGlowClass = `tier-${tier}-glow`;
  const verdict = verdictFor(tier);

  const barGradient =
    tier === "red"    ? "linear-gradient(90deg, #f87171, #fca5a5)" :
    tier === "yellow" ? "linear-gradient(90deg, #fbbf24, #fde68a)" :
    tier === "green"  ? "linear-gradient(90deg, #4ade80, #86efac)" :
                        "linear-gradient(90deg, #60a5fa, #93c5fd)";

  return (
    <div className="tg-glass tg-glow flex flex-col gap-3">
      <div className="flex items-baseline gap-3">
        <span
          className={`${tierClass} ${tierGlowClass}`}
          style={{
            fontSize: 44,
            fontWeight: 800,
            lineHeight: 1,
            fontVariantNumeric: "tabular-nums",
          }}
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

      {/* Animated score bar with tier gradient */}
      <div
        aria-hidden="true"
        style={{
          height: 5,
          background: "rgba(74, 222, 128, 0.06)",
          borderRadius: 3,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${Math.min(100, Math.max(0, score))}%`,
            height: "100%",
            background: barGradient,
            backgroundSize: "200% 100%",
            borderRadius: 3,
            animation: "score-bar-shine 3s linear infinite",
            transition: "width 0.6s ease",
          }}
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
  const order: Array<{ k: keyof SeverityCounts; cls: string; label: string; glow?: string }> = [
    { k: "critical", cls: "sev-chip-critical", label: "Critical", glow: "sev-glow-critical" },
    { k: "high",     cls: "sev-chip-high",     label: "High",     glow: "sev-glow-high" },
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
        <span
          key={o.k}
          className={`tg-chip ${o.cls} ${o.glow ?? ""}`}
          style={{ transition: "box-shadow 0.3s ease" }}
        >
          {counts[o.k]} {o.label}
        </span>
      ))}
    </div>
  );
}

function FindingRow({ finding, delayIndex }: { finding: Finding; delayIndex: number }) {
  const [expanded, setExpanded] = useState(false);
  const sev = finding.severity.toLowerCase();
  const sevClass =
    sev === "critical" ? "sev-chip-critical"
    : sev === "high"   ? "sev-chip-high"
    : sev === "medium" ? "sev-chip-medium"
    : sev === "low"    ? "sev-chip-low"
                       : "sev-chip-info";
  const sevGlow =
    sev === "critical" ? "sev-glow-critical"
    : sev === "high"   ? "sev-glow-high"
                       : "";
  const similar = finding.metadata?.similar_incidents ?? [];
  const hasDetails = !!finding.description || similar.length > 0;

  return (
    <li
      className="tg-glass"
      style={{
        padding: 12,
        cursor: hasDetails ? "pointer" : "default",
        transition: "border-color 0.2s ease, box-shadow 0.2s ease",
        animationDelay: `${0.3 + delayIndex * 0.05}s`,
      }}
      onClick={() => hasDetails && setExpanded(!expanded)}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className={`tg-chip ${sevClass} ${sevGlow}`}>{sev}</span>
        {finding.poc_validated && (
          <span className="tg-chip sev-chip-good">poc ok</span>
        )}
        <span className="text-[10px]" style={{ color: "var(--hb-text-muted)" }}>
          {finding.source_engine}{finding.line != null && `:${finding.line}`}
        </span>
        {hasDetails && (
          <span
            className="ml-auto text-[10px]"
            style={{
              color: "var(--hb-text-muted)",
              transition: "transform 0.2s ease",
              transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
            }}
          >
            ›
          </span>
        )}
      </div>
      <p className="mt-2 text-xs font-medium leading-snug" style={{ color: "var(--hb-text-hi)" }}>
        {finding.title}
      </p>
      <div
        style={{
          maxHeight: expanded ? 600 : 0,
          opacity: expanded ? 1 : 0,
          overflow: "hidden",
          transition: "max-height 0.3s ease, opacity 0.25s ease",
        }}
      >
        {finding.description && (
          <p className="mt-2 text-[11px] leading-relaxed" style={{ color: "var(--hb-text-dim)" }}>
            {finding.description}
          </p>
        )}
        {similar.length > 0 && <SimilarIncidents incidents={similar} />}
      </div>
    </li>
  );
}

function SimilarIncidents({ incidents }: { incidents: SimilarIncident[] }) {
  return (
    <div
      className="mt-2 border-t pt-2"
      style={{ borderColor: "rgba(74, 222, 128, 0.12)" }}
    >
      <p
        className="text-[10px] uppercase"
        style={{ color: "var(--hb-text-dim)", letterSpacing: "0.08em" }}
      >
        Похожие реальные эксплойты
      </p>
      <ul className="mt-1.5 flex flex-col gap-1.5">
        {incidents.map((i) => (
          <li key={i.incident_id}>
            <a
              href={i.url}
              target="_blank"
              rel="noopener noreferrer"
              className="tg-glass text-[11px]"
              style={{
                color: "var(--hb-primary)",
                textDecoration: "none",
                lineHeight: 1.4,
                display: "block",
                padding: "8px 10px",
                transition: "border-color 0.2s ease, background 0.2s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "rgba(74, 222, 128, 0.3)";
                e.currentTarget.style.background = "rgba(74, 222, 128, 0.04)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "rgba(74, 222, 128, 0.12)";
                e.currentTarget.style.background = "rgba(15, 26, 15, 0.6)";
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
