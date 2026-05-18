import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — инциденты" };
export const dynamic = "force-dynamic";

type Incident = {
  id: string;
  title: string;
  summary: string;
  url: string;
  source: string;
  extra_sources: string[];
  extra_urls: string[];
  published_at: string;
  loss_usd: number | null;
};

type Payload = { incidents: Incident[]; total: number };

const SOURCE_LABEL: Record<string, string> = {
  rekt: "Rekt News",
  slowmist: "SlowMist",
  defillama: "DefiLlama",
};

const SOURCE_COLOR: Record<string, string> = {
  rekt: "border-red-500/60 text-red-400",
  slowmist: "border-blue-500/60 text-blue-400",
  defillama: "border-purple-500/60 text-purple-400",
};

async function fetchIncidents(): Promise<Payload | null> {
  const apiUrl = process.env.WR3_API_URL ?? "http://localhost:8001";
  try {
    const r = await fetch(`${apiUrl}/v1/public/incidents?limit=30&days=120`, {
      cache: "no-store",
    });
    if (!r.ok) return null;
    return (await r.json()) as Payload;
  } catch {
    return null;
  }
}

export default async function IncidentsPage() {
  const data = await fetchIncidents();

  return (
    <TerminalPageShell title="Инциденты" eyebrow="// feed">
      <p className="text-[#8bb88b] text-sm leading-relaxed">
        Лента эксплойтов из Rekt News, SlowMist и DefiLlama. Дубликаты схлопываем
        по семантическому сходству, поэтому один и тот же хак из разных источников
        не дублируется.
      </p>

      {data === null ? (
        <div className="glass-card mt-6 border-red-500/30 bg-red-500/5">
          <p className="text-red-400 text-[13px] px-4 py-3">
            Лента инцидентов сейчас недоступна. Попробуйте обновить через минуту.
          </p>
        </div>
      ) : data.incidents.length === 0 ? (
        <p className="text-[#8bb88b] text-[13px] mt-6">
          Лента пуста. Следующее обновление — в течение 6 часов.
        </p>
      ) : (
        <>
          <p className="text-[#547654] text-xs mt-2">
            Всего в базе: {data.total} · показано {data.incidents.length}
          </p>
          <ul className="list-none p-0 mt-4 flex flex-col gap-3">
            {data.incidents.map((incident, idx) => (
              <IncidentRow key={incident.id} incident={incident} index={idx} />
            ))}
          </ul>
        </>
      )}
    </TerminalPageShell>
  );
}

function IncidentRow({ incident, index }: { incident: Incident; index: number }) {
  const allSources = [incident.source, ...incident.extra_sources];
  const isHighLoss = incident.loss_usd != null && incident.loss_usd >= 1_000_000;

  return (
    <li
      className="glass-card hover-lift animate-fade-in-up p-4 rounded-lg"
      style={{ animationDelay: `${index * 60}ms`, animationFillMode: "both" }}
    >
      <div className="flex items-center flex-wrap gap-2 mb-2">
        {allSources.map((s) => (
          <span
            key={s}
            className={`text-[9px] uppercase tracking-wider border px-2 py-0.5 rounded ${SOURCE_COLOR[s] ?? "border-[#547654] text-[#8bb88b]"}`}
          >
            {SOURCE_LABEL[s] ?? s}
          </span>
        ))}
        <span className="text-[#547654] text-[10px] ml-auto">
          {relTime(incident.published_at)}
        </span>
      </div>

      <a
        href={incident.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[#d4ffd4] text-[13px] font-bold no-underline block mb-1 hover:text-[#4ade80] transition-colors"
      >
        {incident.title}
      </a>

      {incident.loss_usd != null && (
        <p
          className={`text-red-400 text-[11px] my-0.5 mb-1.5 font-semibold ${isHighLoss ? "drop-shadow-[0_0_6px_rgba(248,113,113,0.5)]" : ""}`}
        >
          ${formatLoss(incident.loss_usd)}
        </p>
      )}

      {incident.summary && (
        <p className="text-[#a8e6a8] text-[11px] leading-relaxed m-0">
          {truncate(incident.summary, 240)}
        </p>
      )}
    </li>
  );
}

function relTime(iso: string): string {
  const t = new Date(iso).getTime();
  const diff = Date.now() - t;
  const day = 86_400_000;
  if (diff < day) return "сегодня";
  if (diff < 7 * day) return `${Math.floor(diff / day)}д назад`;
  if (diff < 30 * day) return `${Math.floor(diff / (7 * day))}нед назад`;
  return new Date(iso).toLocaleDateString("ru-RU");
}

function formatLoss(usd: number): string {
  if (usd >= 1_000_000_000) return `${(usd / 1_000_000_000).toFixed(1)}B`;
  if (usd >= 1_000_000) return `${(usd / 1_000_000).toFixed(1)}M`;
  if (usd >= 1_000) return `${(usd / 1_000).toFixed(0)}K`;
  return usd.toString();
}

function truncate(s: string, max: number): string {
  return s.length <= max ? s : s.slice(0, max).trimEnd() + "…";
}
