import Link from "next/link";
import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — leaderboard" };

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
const MUTED = "#5a8a5a";
const DIM = "#3a5e3a";
const FG = "#a8e6a8";

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
    <TerminalPageShell title="leaderboard">
      <p style={{ color: MUTED, fontSize: 12 }}>
        // public scans, sorted by score. opted-out users are excluded.
      </p>

      {stats && (
        <section
          style={{
            marginTop: 16,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: 12,
          }}
        >
          <Stat label="scans completed" value={stats.total_scans.toString()} />
          <Stat
            label="avg score"
            value={stats.avg_score != null ? stats.avg_score.toFixed(1) : "—"}
          />
          <Stat label="critical found" value={stats.critical_findings.toString()} accent />
          <Stat label="high found" value={stats.high_findings.toString()} />
          <Stat label="networks" value={stats.networks_count.toString()} />
        </section>
      )}

      <section style={{ marginTop: 24, overflowX: "auto" }}>
        {scans.length === 0 ? (
          <p
            style={{
              color: MUTED,
              fontSize: 12,
              textAlign: "center",
              padding: "40px 0",
            }}
          >
            // no completed scans yet. run the first one via{" "}
            <a href="https://t.me/KitronBot" style={{ color: PRIMARY }}>
              @KitronBot
            </a>
            .
          </p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${DIM}` }}>
                <Th>#</Th>
                <Th>contract</Th>
                <Th>chain</Th>
                <Th align="right">score</Th>
                <Th align="right">findings</Th>
                <Th>author</Th>
                <Th align="right">when</Th>
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

      <p style={{ color: DIM, fontSize: 10, marginTop: 24 }}>
        // opted-out of public listing? open <Link href="/tg/owner" style={{ color: MUTED }}>cfg</Link> in the
        Mini App and flip <code>anonymous_in_public</code>.
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
          fontSize: 10,
          margin: 0,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}
      >
        // {label}
      </p>
      <p
        style={{
          color: accent ? "#f87171" : FG,
          fontSize: 22,
          fontWeight: 700,
          margin: "4px 0 0",
          lineHeight: 1,
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
          {scan.author ? `@${scan.author}` : "anon"}
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
  if (min < 1) return "now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}
