import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — инциденты" };
export const dynamic = "force-dynamic";

const HI = "#d4ffd4";
const MUTED = "#5a8a5a";
const DIM = "#3a5e3a";
const FG = "#a8e6a8";
const ERR = "#f87171";

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
    <TerminalPageShell title="инциденты">
      <p style={{ color: MUTED, fontSize: 12 }}>
        // живой фид DeFi-эксплойтов — Rekt News + SlowMist + DefiLlama Hacks.
        Дедуп через embedding-сходство на api.navy (text-embedding-3-small).
      </p>

      {data === null ? (
        <p style={{ color: ERR, fontSize: 12, marginTop: 24 }}>
          ERR не удалось загрузить ленту инцидентов
        </p>
      ) : data.incidents.length === 0 ? (
        <p style={{ color: MUTED, fontSize: 12, marginTop: 24 }}>
          пока пусто — ждём первый refresh пайплайна
        </p>
      ) : (
        <>
          <p style={{ color: DIM, fontSize: 11, marginTop: 8 }}>
            // всего записей в БД: {data.total} · показано {data.incidents.length}
          </p>
          <ul
            style={{
              listStyle: "none",
              padding: 0,
              margin: "16px 0 0",
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            {data.incidents.map((i) => (
              <IncidentRow key={i.id} incident={i} />
            ))}
          </ul>
        </>
      )}
    </TerminalPageShell>
  );
}

function IncidentRow({ incident }: { incident: Incident }) {
  const allSources = [incident.source, ...incident.extra_sources];
  return (
    <li
      style={{
        background: "#0a0e0a",
        border: `1px solid ${DIM}`,
        borderRadius: 6,
        padding: 14,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 6 }}>
        {allSources.map((s) => (
          <span
            key={s}
            style={{
              color: MUTED,
              fontSize: 9,
              border: `1px solid ${DIM}`,
              padding: "1px 6px",
              borderRadius: 3,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            {SOURCE_LABEL[s] ?? s}
          </span>
        ))}
        <span style={{ color: DIM, fontSize: 10, marginLeft: "auto" }}>
          {relTime(incident.published_at)}
        </span>
      </div>
      <a
        href={incident.url}
        target="_blank"
        rel="noopener noreferrer"
        style={{
          color: HI,
          fontSize: 13,
          fontWeight: 700,
          textDecoration: "none",
          display: "block",
          marginBottom: 4,
        }}
      >
        {incident.title}
      </a>
      {incident.loss_usd != null && (
        <p style={{ color: "#f87171", fontSize: 11, margin: "2px 0 6px" }}>
          ${formatLoss(incident.loss_usd)}
        </p>
      )}
      {incident.summary && (
        <p style={{ color: FG, fontSize: 11, lineHeight: 1.6, margin: 0 }}>
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
