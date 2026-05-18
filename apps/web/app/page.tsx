import Link from "next/link";
import { HeroWithFeed } from "@/components/hero-with-feed";

// Live stats from the API. SSR — no fetch in the browser.
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
    const r = await fetch(`${apiUrl}/v1/public/stats`, {
      next: { revalidate: 60 },
    });
    if (!r.ok) return null;
    return r.json();
  } catch {
    return null;
  }
}

export const revalidate = 60;

export default async function HomePage() {
  const stats = await fetchStats();

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* ─── Compact Header ─── */}
      <header className="flex-shrink-0 z-50 backdrop-blur-xl bg-[#0a0e0a]/80 border-b border-[rgba(74,222,128,0.1)]">
        <div className="max-w-[1600px] mx-auto px-4 lg:px-6 h-12 flex items-center justify-between">
          <Link
            href="/"
            className="font-mono text-[#4ade80] font-bold text-base tracking-tight hover:opacity-80 transition-opacity"
          >
            wr3
            <span className="ml-2 text-[10px] text-[#547654] font-normal">audit engine</span>
          </Link>

          <nav className="flex items-center gap-5 text-xs">
            <Link href="/incidents" className="text-[#547654] hover:text-[#8bb88b] transition-colors">
              Инциденты
            </Link>
            <Link href="/leaderboard" className="text-[#547654] hover:text-[#8bb88b] transition-colors">
              Лидерборд
            </Link>
            <Link href="/pricing" className="text-[#547654] hover:text-[#8bb88b] transition-colors">
              Тарифы
            </Link>
            <a
              href="https://t.me/KitronBot"
              className="px-3 py-1.5 bg-[#4ade80] text-[#0a0e0a] text-[11px] font-bold rounded-md hover:bg-[#6ee7a0] transition-colors"
            >
              TG Bot
            </a>
          </nav>
        </div>
      </header>

      {/* ─── Main: full remaining height, no scroll ─── */}
      <main className="flex-1 min-h-0 overflow-hidden">
        <div className="h-full max-w-[1600px] mx-auto px-4 lg:px-6 py-4 flex flex-col gap-3">

          {/* ─── Stats Strip ─── */}
          {stats && (
            <div className="flex-shrink-0 flex items-center gap-6 px-4 py-2.5 rounded-xl border border-[rgba(74,222,128,0.08)] bg-[rgba(10,14,10,0.5)]">
              <MiniStat label="Сканов" value={String(stats.total_scans)} />
              <div className="w-px h-5 bg-[#547654]/30" />
              <MiniStat
                label="Score"
                value={stats.avg_score != null ? stats.avg_score.toFixed(1) : "—"}
              />
              <div className="w-px h-5 bg-[#547654]/30" />
              <MiniStat label="Critical" value={String(stats.critical_findings)} color="#f87171" />
              <div className="w-px h-5 bg-[#547654]/30" />
              <MiniStat label="High" value={String(stats.high_findings)} color="#fbbf24" />
              <div className="w-px h-5 bg-[#547654]/30" />
              <MiniStat label="Сетей" value={String(stats.networks_count)} />
              <div className="flex-1" />
              <span className="text-[9px] text-[#547654] font-mono">
                Free: 1/day
              </span>
            </div>
          )}

          {/* ─── Dashboard Grid: Scan + Feed ─── */}
          <div className="flex-1 min-h-0">
            <HeroWithFeed />
          </div>

        </div>
      </main>

      {/* ─── Minimal footer ─── */}
      <footer className="flex-shrink-0 border-t border-[rgba(74,222,128,0.06)] px-4 py-2">
        <div className="max-w-[1600px] mx-auto flex items-center justify-between text-[10px] text-[#547654]">
          <span>2026 wr3 · AI-аудит best-effort</span>
          <div className="flex gap-4">
            <a href="https://github.com/StarDust1508/WR3" className="hover:text-[#8bb88b]">GitHub</a>
            <Link href="/legal/tos" className="hover:text-[#8bb88b]">Условия</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function MiniStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-[#547654] uppercase tracking-wider">{label}</span>
      <span
        className="text-sm font-bold tabular-nums"
        style={{ color: color ?? "#d4ffd4" }}
      >
        {value}
      </span>
    </div>
  );
}
