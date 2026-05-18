import Link from "next/link";
import { HeroWithFeed } from "@/components/hero-with-feed";

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
    <div className="flex h-screen flex-col overflow-hidden bg-[#060a06]">
      {/* ─── Header ─── */}
      <header className="flex-shrink-0 z-50 border-b border-[#1a2e1a]/60 bg-[#080c08]/90 backdrop-blur-md">
        <div className="mx-auto max-w-[1440px] px-5 lg:px-8 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <span className="font-mono text-xl font-black text-[#4ade80] tracking-tight">
              wr3
            </span>
            <span className="hidden sm:block h-4 w-px bg-[#1a2e1a]" />
            <span className="hidden sm:block text-xs text-[#547654]">
              AI Audit Engine
            </span>
          </Link>

          <nav className="flex items-center gap-6">
            <Link href="/leaderboard" className="text-sm text-[#6b8f6b] hover:text-[#a8e6a8] transition-colors">
              Лидерборд
            </Link>
            <Link href="/incidents" className="text-sm text-[#6b8f6b] hover:text-[#a8e6a8] transition-colors hidden sm:block">
              Инциденты
            </Link>
            <Link href="/pricing" className="text-sm text-[#6b8f6b] hover:text-[#a8e6a8] transition-colors hidden sm:block">
              Тарифы
            </Link>
            <a
              href="https://t.me/KitronBot"
              className="px-4 py-2 bg-[#4ade80] text-[#060a06] text-sm font-bold rounded-lg hover:bg-[#6ee7a0] transition-all hover:shadow-[0_0_20px_rgba(74,222,128,0.3)]"
            >
              Telegram Bot
            </a>
          </nav>
        </div>
      </header>

      {/* ─── Stats Bar ─── */}
      {stats && (
        <div className="flex-shrink-0 border-b border-[#1a2e1a]/40 bg-[#080c08]/60">
          <div className="mx-auto max-w-[1440px] px-5 lg:px-8 py-2.5 flex items-center gap-8 overflow-x-auto">
            <StatPill label="Сканов" value={String(stats.total_scans)} />
            <StatPill
              label="Avg Score"
              value={stats.avg_score != null ? stats.avg_score.toFixed(1) : "—"}
            />
            <StatPill label="Critical" value={String(stats.critical_findings)} color="#f87171" />
            <StatPill label="High" value={String(stats.high_findings)} color="#fbbf24" />
            <StatPill label="Сетей" value={String(stats.networks_count)} />
          </div>
        </div>
      )}

      {/* ─── Main Dashboard ─── */}
      <main className="flex-1 min-h-0">
        <div className="h-full mx-auto max-w-[1440px] px-5 lg:px-8 py-5">
          <HeroWithFeed />
        </div>
      </main>

      {/* ─── Footer ─── */}
      <footer className="flex-shrink-0 border-t border-[#1a2e1a]/30 bg-[#060a06] px-5 py-2">
        <div className="mx-auto max-w-[1440px] flex items-center justify-between text-xs text-[#3d5c3d]">
          <span>2026 wr3 · AI-аудит best-effort</span>
          <div className="flex gap-4">
            <a href="https://github.com/StarDust1508/WR3" className="hover:text-[#6b8f6b] transition-colors">GitHub</a>
            <Link href="/legal/tos" className="hover:text-[#6b8f6b] transition-colors">Условия</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

function StatPill({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center gap-2 whitespace-nowrap">
      <span className="text-xs text-[#3d5c3d] uppercase tracking-wide">{label}</span>
      <span className="text-base font-bold tabular-nums" style={{ color: color ?? "#a8e6a8" }}>
        {value}
      </span>
    </div>
  );
}
