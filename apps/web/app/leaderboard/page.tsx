import Link from "next/link";
import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — лидерборд" };

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
      <p className="text-[#8bb88b] text-base leading-relaxed">
        Публичные сканы, отсортированные по score. Пользователи с включённой
        анонимностью здесь не показываются.
      </p>

      {stats && (
        <section className="mt-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <StatCard label="Сканов завершено" value={stats.total_scans.toString()} />
          <StatCard
            label="Средний score"
            value={stats.avg_score != null ? stats.avg_score.toFixed(1) : "—"}
          />
          <StatCard label="Critical" value={stats.critical_findings.toString()} accent />
          <StatCard label="High" value={stats.high_findings.toString()} />
          <StatCard label="Сетей" value={stats.networks_count.toString()} />
        </section>
      )}

      <section className="mt-8 overflow-x-auto">
        {scans.length === 0 ? (
          <div className="glass-card p-10 text-center">
            <p className="text-[#8bb88b] text-base">
              Ещё нет завершённых сканов. Запустите первый через{" "}
              <a
                href="https://t.me/KitronBot"
                className="text-[#4ade80] underline"
              >
                @KitronBot
              </a>
              .
            </p>
          </div>
        ) : (
          <div className="rounded-2xl border border-[#1a2e1a]/60 bg-[#0c120c] overflow-hidden">
            <table className="w-full border-collapse text-sm tabular-nums">
              <thead>
                <tr className="border-b border-[#547654]/50">
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
          </div>
        )}
      </section>

      <p className="text-[#6b8f6b] text-sm mt-8">
        Не хотите попадать в лидерборд? Откройте{" "}
        <Link href="/tg/owner" className="text-[#4ade80] underline">
          настройки в Mini App
        </Link>{" "}
        и включите анонимность в публичном.
      </p>
    </TerminalPageShell>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-[#1a2e1a]/60 bg-[#0c120c] p-4 animate-fade-in-up">
      <p className="text-[#8bb88b] text-xs m-0 uppercase tracking-wider font-semibold">
        {label}
      </p>
      <p
        className={`text-3xl font-extrabold mt-2 mb-0 leading-none tabular-nums ${accent ? "text-red-400 drop-shadow-[0_0_8px_rgba(248,113,113,0.4)]" : "text-[#d4ffd4]"}`}
      >
        {value}
      </p>
    </div>
  );
}

function Th({ children, align }: { children: React.ReactNode; align?: "left" | "right" }) {
  return (
    <th
      className={`px-4 py-3 text-[#8bb88b] font-bold text-xs uppercase tracking-wider ${align === "right" ? "text-right" : "text-left"}`}
    >
      {children}
    </th>
  );
}

function Row({ index, scan }: { index: number; scan: PublicScan }) {
  const tierColor =
    scan.tier === "red"
      ? "text-red-400"
      : scan.tier === "yellow"
        ? "text-yellow-400"
        : scan.tier === "green"
          ? "text-[#4ade80]"
          : scan.tier === "blue"
            ? "text-blue-400"
            : "text-[#a8e6a8]";

  const rankDisplay = index <= 3;

  return (
    <tr
      className="border-b border-[#547654]/30 hover:bg-[#4ade80]/5 transition-colors animate-fade-in-up"
      style={{ animationDelay: `${index * 40}ms`, animationFillMode: "both" }}
    >
      <td className="px-4 py-3">
        {rankDisplay ? (
          <span className="text-gradient font-extrabold text-base">
            {String(index).padStart(2, "0")}
          </span>
        ) : (
          <span className="text-[#8bb88b]">{String(index).padStart(2, "0")}</span>
        )}
      </td>
      <td className="px-4 py-3">
        <Link
          href={`/scan/${scan.id}`}
          className="text-[#a8e6a8] no-underline font-mono text-sm hover:text-[#4ade80] transition-colors"
        >
          {shortAddr(scan.address)}
        </Link>
      </td>
      <td className="px-4 py-3">
        <span className="text-[#8bb88b] text-sm">{scan.network}</span>
      </td>
      <td className="px-4 py-3 text-right">
        <span className={`${tierColor} font-bold text-base`}>
          {scan.score != null ? scan.score.toFixed(0) : "—"}
        </span>
      </td>
      <td className="px-4 py-3 text-right">
        <span className="text-[#8bb88b] text-sm">{scan.findings_total}</span>
      </td>
      <td className="px-4 py-3">
        <span className={`text-sm ${scan.author ? "text-[#8bb88b]" : "text-[#547654]"}`}>
          {scan.author ? `@${scan.author}` : "аноним"}
        </span>
      </td>
      <td className="px-4 py-3 text-right">
        <span className="text-[#547654] text-xs">{relTime(scan.completed_at)}</span>
      </td>
    </tr>
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
