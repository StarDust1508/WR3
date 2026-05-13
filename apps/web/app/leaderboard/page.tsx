import Link from "next/link";
import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — лидерборд" };

// Disable any caching — leaderboard should always show fresh data.
export const dynamic = "force-dynamic";
export const revalidate = 0;

type PublicScan = {
  id: string;
  address: string;
  network: string;
  score: number | null;
  tier: string | null;
  findings_total: number;
  duration_seconds: number | null;
  completed_at: string | null;
  author: string | null;
};

type PublicStats = {
  total_scans: number;
  avg_score: number | null;
  critical_findings: number;
  high_findings: number;
  networks_count: number;
};

const PRIMARY = "#4ade80";
const MUTED = "#8bb88b";
const DIM = "#547654";
const FG = "#a8e6a8";
const HI = "#d4ffd4";

async function fetchStats(): Promise<PublicStats | null> {
  const apiUrl = process.env.WR3_API_URL ?? "http://localhost:8001";
  try {
    const r = await fetch(`${apiUrl}/v1/public/stats`, { cache: "no-store" });
    if (!r.ok) return null;
    return r.json();
  } catch {
    return null;
  }
}

async function fetchScans(): Promise<PublicScan[]> {
  const apiUrl = process.env.WR3_API_URL ?? "http://localhost:8001";
  try {
    const r = await fetch(`${apiUrl}/v1/public/scans?limit=50`, { cache: "no-store" });
    if (!r.ok) return [];
    return r.json();
  } catch {
    return [];
  }
}

export default async function LeaderboardPage() {
  const [stats, scans] = await Promise.all([fetchStats(), fetchScans()]);

  return (
    <TerminalPageShell title="Лидерборд" eyebrow="// scans">
      <p style={{ color: MUTED, fontSize: 14, lineHeight: 1.6 }}>
        Публичные сканы, отсортированные по score. Пользователи с включённой
        анонимностью здесь не показываются.
      </p>

      {stats && (
        <section
          style={{
            marginTop: 24,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: 12,
          }}
        >
          <Stat label="Сканов завершено" value={stats.total_scans.toString()} />
          <Stat
            label="Средний score"
            value={stats.avg_score != null ? stats.avg_score.toFixed(1) : "—"}
          />
          <Stat label="Critical" value={stats.critical_findings.toString()} accent />
          <Stat label="High" value={stats.high_findings.toString()} />
          <Stat label="Сетей" value={stats.networks_count.toString()} />
        </section>
      )}

      <section style={{ marginTop: 32, overflowX: "auto" }}>
        {scans.length === 0 ? (
          <p
            style={{
              color: MUTED,
              fontSize: 13,
              textAlign: "center",
              padding: "40px 0",
            }}
          >
            Ещё нет завершённых сканов. Запустите первый через{" "}
            <a
              href="https://t.me/KitronBot"
              style={{ color: PRIMARY, textDecoration: "underline" }}
            >
              @KitronBot
            </a>
            .
          </p>
        ) : (
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 13,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            <thead>
              <tr style={{ borderBottom: `1px solid ${DIM}` }}>
                <Th>#</Th>
                <Th>Контракт</Th>
                <Th>Сеть</Th>
                <Th align="right">Score</Th>
                <Th align="right">Находок</Th>
                <Th>Автор</Th>
                <Th align="right">Когда</Th>
              </tr>
            </thead>
            <tbody>
              {scans.map((s, i) => (
                <Row key={s.id} index={i + 1} scan={s} />
              ))}
            </tbody>
          </table>
        )}
      </section>

      <p style={{ color: MUTED, fontSize: 12, marginTop: 32 }}>
        Не хотите попадать в лидерборд? Откройте{" "}
        <Link href="/tg/owner" style={{ color: PRIMARY, textDecoration: "underline" }}>
          настройки в Mini App
        </Link>{" "}
        и включите анонимность в публичном.
      </p>
    </TerminalPageShell>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div
      style={{
        background: "#0a0e0a",
        border: `1px solid ${DIM}`,
        borderRadius: 4,
        padding: 12,
      }}
    >
      <p
        style={{
          color: MUTED,
          fontSize: 11,
          margin: 0,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </p>
      <p
        style={{
          color: accent ? "#f87171" : HI,
          fontSize: 26,
          fontWeight: 800,
          margin: "6px 0 0",
          lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </p>
    </div>
  );
}

function Th({ children, align }: { children: React.ReactNode; align?: "left" | "right" }) {
  return (
    <th
      style={{
        textAlign: align ?? "left",
        padding: "8px 6px",
        color: MUTED,
        fontWeight: 700,
        fontSize: 10,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
      }}
    >
      {children}
    </th>
  );
}

function Row({ index, scan }: { index: number; scan: PublicScan }) {
  const tierColor =
    scan.tier === "red"
      ? "#f87171"
      : scan.tier === "yellow"
        ? "#fbbf24"
        : scan.tier === "green"
          ? PRIMARY
          : scan.tier === "blue"
            ? "#60a5fa"
            : FG;
  return (
    <tr style={{ borderBottom: `1px solid ${DIM}` }}>
      <Td>
        <span style={{ color: MUTED }}>{String(index).padStart(2, "0")}</span>
      </Td>
      <Td>
        <Link
          href={`/scan/${scan.id}`}
          style={{ color: FG, textDecoration: "none", fontFamily: "inherit" }}
        >
          {shortAddr(scan.address)}
        </Link>
      </Td>
      <Td>
        <span style={{ color: MUTED, fontSize: 11 }}>{scan.network}</span>
      </Td>
      <Td align="right">
        <span style={{ color: tierColor, fontWeight: 700, fontSize: 13 }}>
          {scan.score != null ? scan.score.toFixed(0) : "—"}
        </span>
      </Td>
      <Td align="right">
        <span style={{ color: MUTED, fontSize: 11 }}>{scan.findings_total}</span>
      </Td>
      <Td>
        <span style={{ color: scan.author ? MUTED : DIM, fontSize: 11 }}>
          {scan.author ? `@${scan.author}` : "аноним"}
        </span>
      </Td>
      <Td align="right">
        <span style={{ color: DIM, fontSize: 10 }}>{relTime(scan.completed_at)}</span>
      </Td>
    </tr>
  );
}

function Td({
  children,
  align,
}: {
  children: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <td style={{ padding: "8px 6px", textAlign: align ?? "left", verticalAlign: "middle" }}>
      {children}
    </td>
  );
}

function shortAddr(a: string): string {
  if (a.length <= 12) return a;
  return `${a.slice(0, 6)}…${a.slice(-4)}`;
}

function relTime(iso: string | null): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (!t) return "";
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60_000);
  if (min < 1) return "только что";
  if (min < 60) return `${min} мин назад`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} ч назад`;
  return `${Math.floor(hr / 24)} д назад`;
}
