import Link from "next/link";
import { notFound } from "next/navigation";
import { TRAFFIC_LIGHT, type Tier } from "@wr3/shared";
import { FindingGroups } from "./finding-group";

export const dynamic = "force-dynamic";

interface ScanDetail {
  id: string;
  address: string;
  network: string;
  stage: string;
  progress: number;
  score: number | null;
  tier: Tier | null;
  report: {
    axes?: Array<{ name: string; weight: number; score: number | null; rationale: string }>;
    chain_metadata?: {
      address?: string;
      executable?: boolean;
      loader?: string | null;
      upgradeable?: boolean;
      upgrade_authority?: string | null;
      last_upgrade_slot?: number | null;
      coverage?: {
        engines_ran?: string[];
        engines_expected?: string[];
        engines_missing?: string[];
        source_chars?: number;
        source_truncated?: boolean;
        llm_triage?: boolean;
        poc_enabled?: boolean;
        fuzzing_enabled?: boolean;
        proxy_resolved?: boolean;
        implementation_address?: string | null;
        network_aware?: boolean;
        findings_before_dedup?: number;
        findings_after_dedup?: number;
      };
      audit_warnings?: string[];
    };
    disclaimer?: string;
  } | null;
  duration_seconds: number | null;
  created_at: string;
  completed_at: string | null;
  findings: Array<{
    id: string;
    title: string;
    description: string;
    severity: string;
    source_engine: string;
    file: string | null;
    line: number | null;
    confidence: number;
    dismissed: boolean;
    poc_validated?: boolean;
    poc_path?: string | null;
    metadata?: {
      similar_incidents?: Array<{
        incident_id: string;
        title: string;
        url: string;
        source: string;
        loss_usd: number | null;
        published_at: string;
        similarity: number;
      }>;
    } | null;
  }>;
}

async function fetchScan(id: string): Promise<ScanDetail | null> {
  const apiUrl = process.env.WR3_API_URL ?? "http://localhost:8001";
  try {
    const r = await fetch(`${apiUrl}/v1/scan/${id}`, { cache: "no-store" });
    if (!r.ok) return null;
    return (await r.json()) as ScanDetail;
  } catch {
    return null;
  }
}

function scoreColor(tier: Tier): string {
  switch (tier) {
    case "green":
      return "#4ade80";
    case "yellow":
      return "#facc15";
    case "red":
      return "#f87171";
    default:
      return "#8bb88b";
  }
}

export default async function ScanDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const scan = await fetchScan(id);

  if (!scan) {
    notFound();
  }

  const tier = (scan.tier ?? "yellow") as Tier;
  const light = TRAFFIC_LIGHT[tier];
  const color = scoreColor(tier);
  const active = scan.findings.filter((f) => !f.dismissed);
  const dismissed = scan.findings.filter((f) => f.dismissed);
  const scoreVal = scan.score ?? 0;
  const circumference = 2 * Math.PI * 54;
  const strokeOffset = circumference - (scoreVal / 100) * circumference;

  return (
    <main className="min-h-screen bg-[#0a0e0a] px-6 py-12 text-[#d4ffd4]">
      <div className="mx-auto max-w-5xl">
        {/* Navigation */}
        <nav className="mb-8 text-sm">
          <Link
            href="/"
            className="text-[#8bb88b] transition-colors hover:text-[#4ade80]"
          >
            ← Назад
          </Link>
        </nav>

        {/* Header */}
        <header className="mb-10 animate-fade-in-up">
          <div className="flex items-center gap-4">
            <h1 className="font-mono text-lg tracking-tight text-[#d4ffd4]">
              {scan.address}
            </h1>
            <span className="rounded-full border border-[#4ade80]/30 bg-[#4ade80]/10 px-3 py-0.5 font-mono text-xs uppercase text-[#4ade80]">
              {scan.network}
            </span>
          </div>
          <p className="mt-2 text-sm text-[#547654]">
            Просканировано {new Date(scan.created_at).toLocaleString("ru-RU")}
            {scan.duration_seconds != null && ` · ${scan.duration_seconds.toFixed(1)}с`}
          </p>
          <a
            href={`/api/v1/scan/${scan.id}/report.md`}
            className="mt-3 inline-block rounded-full border border-[#4ade80]/30 bg-[#4ade80]/5 px-4 py-1.5 text-xs text-[#4ade80] transition-all hover:border-[#4ade80]/60 hover:bg-[#4ade80]/10 hover:shadow-[0_0_12px_rgba(74,222,128,0.15)]"
            download
          >
            ↓ скачать отчёт
          </a>
        </header>

        {/* Audit Warnings */}
        {scan.report?.chain_metadata?.audit_warnings && scan.report.chain_metadata.audit_warnings.length > 0 && (
          <AuditWarnings warnings={scan.report.chain_metadata.audit_warnings} />
        )}

        {/* Coverage + Proxy Banner */}
        <CoverageBanner
          coverage={scan.report?.chain_metadata?.coverage}
        />

        {/* Solana Metadata */}
        {scan.report?.chain_metadata?.executable !== undefined && (
          <SolanaMeta meta={scan.report.chain_metadata} />
        )}

        {/* Score + Axes Section */}
        <section className="glass-card mb-10 grid grid-cols-1 gap-8 p-8 md:grid-cols-[220px_1fr]">
          {/* Radial Gauge */}
          <div className="flex flex-col items-center justify-center">
            <div className="relative h-36 w-36">
              <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
                <circle
                  cx="60"
                  cy="60"
                  r="54"
                  fill="none"
                  stroke="#1a2e1a"
                  strokeWidth="8"
                />
                <circle
                  cx="60"
                  cy="60"
                  r="54"
                  fill="none"
                  stroke={color}
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={circumference}
                  strokeDashoffset={strokeOffset}
                  style={{ transition: "stroke-dashoffset 1s ease-out" }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-4xl font-bold" style={{ color }}>
                  {scan.score ?? "—"}
                </span>
                <span className="mt-1 text-xs uppercase tracking-wider" style={{ color }}>
                  {light.label}
                </span>
              </div>
            </div>
            <p className="mt-3 text-xs text-[#547654]">из 100</p>
          </div>

          {/* Axes Bars */}
          <div>
            <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-[#8bb88b]">
              Разбивка по осям
            </p>
            <div className="space-y-3">
              {(scan.report?.axes ?? []).map((a) => {
                const pending = a.weight === 0 || a.score === null;
                const barWidth = a.score != null ? a.score : 0;
                return (
                  <div key={a.name} className="group">
                    <div className="mb-1 flex items-baseline justify-between text-sm">
                      <span className={pending ? "text-[#547654]" : "text-[#d4ffd4]"}>
                        {a.name}
                      </span>
                      <span className="font-mono text-xs text-[#8bb88b]">
                        {a.score === null ? "—" : a.score.toFixed(1)}
                        {!pending && (
                          <span className="ml-2 text-[#547654]">
                            ({Math.round(a.weight * 100)}%)
                          </span>
                        )}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-[#1a2e1a]">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{
                          width: `${barWidth}%`,
                          backgroundColor: pending ? "#547654" : color,
                          opacity: pending ? 0.4 : 1,
                        }}
                      />
                    </div>
                    {a.rationale && (
                      <p className="mt-0.5 truncate text-xs text-[#547654]">
                        {a.rationale}
                        {pending && " (не считается в общий score)"}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Active Findings */}
        <section className="mb-10">
          <h2 className="mb-5 text-lg font-semibold text-[#d4ffd4]">
            Активные находки{" "}
            <span className="text-[#547654]">({active.length})</span>
          </h2>
          {active.length === 0 ? (
            <p className="text-sm text-[#547654]">
              Активных находок нет. Либо контракт чист, либо все совпадения отфильтрованы
              на триаже.
            </p>
          ) : (
            <FindingGroups findings={active} />
          )}
        </section>

        {/* Dismissed Findings */}
        {dismissed.length > 0 && (
          <section className="mb-10">
            <h2 className="mb-5 text-lg font-semibold text-[#547654]">
              Отфильтровано триажом ({dismissed.length})
            </h2>
            <div className="opacity-50">
              <FindingGroups findings={dismissed} />
            </div>
          </section>
        )}

        {/* Footer */}
        <footer className="mt-12 border-t border-[#1a2e1a] pt-6 text-xs text-[#547654]">
          {scan.report?.disclaimer ?? (
            <p>
              Результаты AI-аудита — best-effort и не заменяют ручное ревью.
              wr3 не даёт гарантий.
            </p>
          )}
        </footer>
      </div>
    </main>
  );
}

function AuditWarnings({ warnings }: { warnings: string[] }) {
  return (
    <section className="mb-6 animate-fade-in-up">
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
        <div className="mb-2 flex items-center gap-2">
          <svg className="h-4 w-4 text-amber-400" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.168 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
          </svg>
          <span className="text-xs font-semibold uppercase tracking-widest text-amber-400">
            Предупреждения аудита
          </span>
        </div>
        <ul className="space-y-1">
          {warnings.map((w, i) => (
            <li key={i} className="text-sm text-amber-200/80">
              {w}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function CoverageBanner({
  coverage,
}: {
  coverage?: {
    engines_ran?: string[];
    engines_expected?: string[];
    engines_missing?: string[];
    source_chars?: number;
    source_truncated?: boolean;
    llm_triage?: boolean;
    poc_enabled?: boolean;
    fuzzing_enabled?: boolean;
    proxy_resolved?: boolean;
    implementation_address?: string | null;
    network_aware?: boolean;
    findings_before_dedup?: number;
    findings_after_dedup?: number;
  };
}) {
  if (!coverage) return null;

  const enginesRan = coverage.engines_ran ?? [];
  const enginesExpected = coverage.engines_expected ?? [];
  const enginesMissing = coverage.engines_missing ?? [];
  const sourceChars = coverage.source_chars ?? 0;
  const truncated = coverage.source_truncated ?? false;
  const proxyResolved = coverage.proxy_resolved ?? false;
  const implAddress = coverage.implementation_address;
  const llmTriage = coverage.llm_triage ?? false;
  const pocEnabled = coverage.poc_enabled ?? false;
  const fuzzingEnabled = coverage.fuzzing_enabled ?? false;
  const networkAware = coverage.network_aware ?? false;
  const beforeDedup = coverage.findings_before_dedup;
  const afterDedup = coverage.findings_after_dedup;
  const dedupMerged = beforeDedup != null && afterDedup != null ? beforeDedup - afterDedup : 0;

  return (
    <section className="mb-6 animate-fade-in-up">
      <div className="rounded-xl border border-[#1a2e1a] bg-[#0c120c] p-4">
        <div className="mb-3 flex items-center gap-2">
          <svg className="h-4 w-4 text-[#4ade80]" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          <span className="text-xs font-semibold uppercase tracking-widest text-[#8bb88b]">
            Покрытие анализа
          </span>
        </div>

        {/* Proxy badge */}
        {proxyResolved && implAddress && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-[#4ade80]/20 bg-[#4ade80]/5 px-3 py-2">
            <span className="text-xs font-semibold text-[#4ade80]">PROXY</span>
            <span className="text-xs text-[#8bb88b]">→</span>
            <span className="font-mono text-xs text-[#d4ffd4]">
              {implAddress.slice(0, 10)}...{implAddress.slice(-8)}
            </span>
            <span className="text-xs text-[#547654]">implementation проанализирован</span>
          </div>
        )}

        {/* Engine status grid */}
        <div className="flex flex-wrap gap-2 mb-3">
          {enginesExpected.map((engine) => {
            const ran = enginesRan.includes(engine);
            return (
              <div
                key={engine}
                className={[
                  "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium",
                  ran
                    ? "border-[#4ade80]/30 bg-[#4ade80]/10 text-[#4ade80]"
                    : "border-red-500/30 bg-red-500/10 text-red-400",
                ].join(" ")}
              >
                {ran ? (
                  <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                ) : (
                  <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                )}
                {engine}
              </div>
            );
          })}

          {/* LLM / PoC / Fuzzing badges */}
          <div className={[
            "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium",
            llmTriage
              ? "border-[#4ade80]/30 bg-[#4ade80]/10 text-[#4ade80]"
              : "border-[#547654]/30 bg-[#547654]/10 text-[#547654]",
          ].join(" ")}>
            {llmTriage ? "✓" : "✗"} LLM triage
          </div>
          <div className={[
            "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium",
            pocEnabled
              ? "border-[#4ade80]/30 bg-[#4ade80]/10 text-[#4ade80]"
              : "border-[#547654]/30 bg-[#547654]/10 text-[#547654]",
          ].join(" ")}>
            {pocEnabled ? "✓" : "✗"} PoC gen
          </div>
          <div className={[
            "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium",
            fuzzingEnabled
              ? "border-[#4ade80]/30 bg-[#4ade80]/10 text-[#4ade80]"
              : "border-[#547654]/30 bg-[#547654]/10 text-[#547654]",
          ].join(" ")}>
            {fuzzingEnabled ? "✓" : "✗"} Fuzzing
          </div>
          {networkAware && (
            <div className="flex items-center gap-1.5 rounded-lg border border-blue-400/30 bg-blue-400/10 px-3 py-1.5 text-xs font-medium text-blue-400">
              ✓ Network-aware
            </div>
          )}
        </div>

        {/* Source info + dedup stats */}
        <div className="flex items-center gap-4 text-xs text-[#547654]">
          <span>
            Исходный код: {sourceChars > 0 ? `${(sourceChars / 1000).toFixed(1)}K символов` : "не найден"}
          </span>
          {truncated && (
            <span className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-amber-400">
              обрезан до 48K для LLM
            </span>
          )}
          {dedupMerged > 0 && (
            <span className="rounded border border-[#4ade80]/20 bg-[#4ade80]/5 px-2 py-0.5 text-[#4ade80]">
              {dedupMerged} дубликатов объединено
            </span>
          )}
        </div>
      </div>
    </section>
  );
}

function SolanaMeta({
  meta,
}: {
  meta: NonNullable<ScanDetail["report"]>["chain_metadata"];
}) {
  if (!meta) return null;
  return (
    <section className="glass-card mb-10 animate-fade-in-up p-6">
      <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-[#8bb88b]">
        Метаданные программы Solana
      </h2>
      <dl className="grid grid-cols-[200px_1fr] gap-y-3 text-sm">
        <dt className="text-[#547654]">Исполняемая</dt>
        <dd className="text-[#d4ffd4]">{meta.executable ? "да" : "нет"}</dd>
        {meta.loader && (
          <>
            <dt className="text-[#547654]">Loader</dt>
            <dd className="break-all font-mono text-xs text-[#8bb88b]">{meta.loader}</dd>
          </>
        )}
        <dt className="text-[#547654]">Обновляемая</dt>
        <dd>
          {meta.upgradeable ? (
            <span className="text-amber-400">
              да (риск централизации)
            </span>
          ) : (
            <span className="text-[#4ade80]">нет — байткод заморожен</span>
          )}
        </dd>
        {meta.upgradeable && meta.upgrade_authority && (
          <>
            <dt className="text-[#547654]">Upgrade authority</dt>
            <dd className="break-all font-mono text-xs text-[#8bb88b]">
              {meta.upgrade_authority}
            </dd>
          </>
        )}
        {meta.upgradeable && meta.last_upgrade_slot != null && (
          <>
            <dt className="text-[#547654]">Последний upgrade slot</dt>
            <dd className="font-mono text-[#d4ffd4]">
              {meta.last_upgrade_slot.toLocaleString("ru-RU")}
            </dd>
          </>
        )}
      </dl>
    </section>
  );
}
