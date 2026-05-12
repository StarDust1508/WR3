import Link from "next/link";
import { notFound } from "next/navigation";
import { TRAFFIC_LIGHT, type Tier } from "@wr3/shared";
import { FindingRow } from "./finding-row";

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
    axes?: Array<{ name: string; weight: number; score: number; rationale: string }>;
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
  const active = scan.findings.filter((f) => !f.dismissed);
  const dismissed = scan.findings.filter((f) => f.dismissed);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <nav className="mb-6 text-sm">
        <Link href="/" className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-50">
          ← Назад
        </Link>
      </nav>

      <header className="mb-10 flex flex-col gap-2">
        <div className="flex items-baseline gap-3">
          <h1 className="font-mono text-lg">{scan.address}</h1>
          <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-xs uppercase dark:bg-zinc-800">
            {scan.network}
          </span>
        </div>
        <p className="text-sm text-zinc-500">
          Просканировано {new Date(scan.created_at).toLocaleString("ru-RU")}
          {scan.duration_seconds != null && ` · ${scan.duration_seconds.toFixed(1)}с`}
        </p>
      </header>

      <section
        className="mb-10 grid grid-cols-1 gap-6 rounded-lg border p-6 md:grid-cols-[200px_1fr]"
        style={{ borderColor: light.color + "33" }}
      >
        <div>
          <p className="text-xs uppercase tracking-wide text-zinc-500">Оценка</p>
          <p className="mt-1 text-6xl font-bold" style={{ color: light.color }}>
            {scan.score ?? "—"}
          </p>
          <p className="mt-1 text-sm" style={{ color: light.color }}>
            {light.label}
          </p>
        </div>
        <div>
          <p className="mb-2 text-xs uppercase tracking-wide text-zinc-500">
            Разбивка по осям
          </p>
          <div className="space-y-2">
            {(scan.report?.axes ?? []).map((a) => (
              <div key={a.name} className="grid grid-cols-[180px_60px_1fr] gap-3 text-sm">
                <span className="text-zinc-700 dark:text-zinc-300">{a.name}</span>
                <span className="font-mono text-zinc-500">{a.score.toFixed(1)}</span>
                <span className="truncate text-zinc-500">
                  {a.rationale} <span className="text-zinc-400">(вес {Math.round(a.weight * 100)}%)</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="mb-4 text-lg font-semibold">
          Активные находки <span className="text-zinc-500">({active.length})</span>
        </h2>
        {active.length === 0 ? (
          <p className="text-sm text-zinc-500">
            Активных находок нет. Либо контракт чист, либо все совпадения отфильтрованы
            на триаже.
          </p>
        ) : (
          <ul className="space-y-2">
            {active.map((f) => (
              <FindingRow key={f.id} finding={f} />
            ))}
          </ul>
        )}
      </section>

      {dismissed.length > 0 && (
        <section className="mb-10">
          <h2 className="mb-4 text-lg font-semibold text-zinc-500">
            Отфильтровано триажом ({dismissed.length})
          </h2>
          <ul className="space-y-2 opacity-60">
            {dismissed.map((f) => (
              <FindingRow key={f.id} finding={f} />
            ))}
          </ul>
        </section>
      )}

      <footer className="mt-12 border-t pt-6 text-xs text-zinc-500 dark:border-zinc-800">
        {scan.report?.disclaimer ?? (
          <p>
            Результаты AI-аудита — best-effort и не заменяют ручное ревью.
            wr3 не даёт гарантий.
          </p>
        )}
      </footer>
    </main>
  );
}
