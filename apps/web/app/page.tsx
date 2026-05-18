import Link from "next/link";
import { ScanInput } from "@/components/scan-input";

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
    <>
      {/* ─── Header ─── */}
      <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-[#0a0e0a]/70 border-b border-[rgba(74,222,128,0.08)]">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link
            href="/"
            className="font-mono text-[#4ade80] font-bold text-lg tracking-tight hover:opacity-80 transition-opacity"
          >
            wr3
          </Link>

          <nav className="hidden md:flex items-center gap-8 text-sm">
            <Link href="/incidents" className="text-[#8bb88b] hover:text-[#d4ffd4] transition-colors">
              Инциденты
            </Link>
            <Link href="/leaderboard" className="text-[#8bb88b] hover:text-[#d4ffd4] transition-colors">
              Лидерборд
            </Link>
            <Link href="/pricing" className="text-[#8bb88b] hover:text-[#d4ffd4] transition-colors">
              Тарифы
            </Link>
            <Link href="/docs" className="text-[#8bb88b] hover:text-[#d4ffd4] transition-colors">
              Документация
            </Link>
            <a
              href="https://t.me/KitronBot"
              className="ml-2 px-4 py-2 bg-[#4ade80] text-[#0a0e0a] text-xs font-bold rounded-lg hover:bg-[#6ee7a0] transition-colors"
            >
              Открыть бот
            </a>
          </nav>
        </div>
      </header>

      <main className="min-h-screen pt-24 pb-16 px-6">
        <div className="max-w-7xl mx-auto">
          {/* ─── Hero Section ─── */}
          <section className="max-w-4xl mx-auto text-center pt-16 pb-20 animate-fade-in-up">
            <p className="font-mono text-xs text-[#547654] uppercase tracking-[0.2em] mb-6">
              AI Security Audit Engine
            </p>

            <h1 className="text-5xl md:text-6xl lg:text-7xl font-extrabold leading-[1.05] tracking-tight mb-6">
              <span className="text-gradient">Найдите уязвимости</span>
              <br />
              <span className="text-[#d4ffd4]">до того, как их найдёт</span>
              <br />
              <span className="text-[#4ade80]">атакующий.</span>
            </h1>

            <p className="text-[#8bb88b] text-lg md:text-xl leading-relaxed max-w-2xl mx-auto mb-10">
              От адреса контракта до полного отчёта за минуту. Multi-engine статика,
              LLM-триаж в 4 параллельных агента, Foundry PoC retry-loop и AI-fuzzing.
              EVM и Solana — в одном пайплайне.
            </p>

            <div className="max-w-xl mx-auto">
              <ScanInput />
            </div>

            <p className="text-[#547654] text-xs mt-5">
              Free — 1 контракт в сутки. Платно от $29/мес: безлимит + полный Foundry PoC.{" "}
              <Link href="/pricing" className="text-[#4ade80] underline underline-offset-2 hover:text-[#d4ffd4]">
                Тарифы
              </Link>
            </p>
          </section>

          {/* ─── Live Stats Strip ─── */}
          {stats && (
            <section className="animate-fade-in-up max-w-4xl mx-auto mb-24" style={{ animationDelay: "200ms" }}>
              <div className="glass-card animate-pulse-glow p-6 grid grid-cols-2 md:grid-cols-5 gap-6">
                <StatCard label="Сканов" value={String(stats.total_scans)} />
                <StatCard
                  label="Средний score"
                  value={stats.avg_score != null ? stats.avg_score.toFixed(1) : "--"}
                />
                <StatCard label="Critical" value={String(stats.critical_findings)} accent="#f87171" />
                <StatCard label="High" value={String(stats.high_findings)} accent="#fbbf24" />
                <StatCard label="Сетей" value={String(stats.networks_count)} />
              </div>
            </section>
          )}

          {/* ─── Features Grid ─── */}
          <section className="max-w-5xl mx-auto mb-32">
            <h2 className="text-center text-2xl md:text-3xl font-bold text-[#d4ffd4] mb-4">
              Почему wr3
            </h2>
            <p className="text-center text-[#8bb88b] text-sm mb-12 max-w-lg mx-auto">
              Комбинация статических анализаторов, LLM-агентов и on-chain данных
            </p>

            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-5">
              <FeatureCard
                icon={<ShieldIcon />}
                title="Multi-engine консенсус"
                description="Aderyn, Slither, Wake работают параллельно. Совпадения в нескольких движках повышают вес находки."
                delay="0ms"
              />
              <FeatureCard
                icon={<BrainIcon />}
                title="LLM-триаж"
                description="4 агента классифицируют, дедуплицируют и ранжируют находки. Минимум ложных срабатываний."
                delay="100ms"
              />
              <FeatureCard
                icon={<ChartIcon />}
                title="Прозрачная оценка"
                description="Шкала 0-100 по 5 осям с открытыми весами. Никаких чёрных ящиков и pay-to-play."
                delay="200ms"
              />
              <FeatureCard
                icon={<GlobeIcon />}
                title="EVM + Solana"
                description="Полная таксономия Sealevel-attacks. Большинство AI-аудиторов пропускают Solana -- wr3 нет."
                delay="300ms"
              />
            </div>
          </section>

          {/* ─── How It Works ─── */}
          <section className="max-w-4xl mx-auto mb-32">
            <h2 className="text-center text-2xl md:text-3xl font-bold text-[#d4ffd4] mb-4">
              Как это работает
            </h2>
            <p className="text-center text-[#8bb88b] text-sm mb-16 max-w-md mx-auto">
              Три шага от адреса до полного аудит-отчёта
            </p>

            <div className="relative grid md:grid-cols-3 gap-8">
              {/* Connecting line */}
              <div className="hidden md:block absolute top-12 left-[16.6%] right-[16.6%] h-px bg-gradient-to-r from-transparent via-[#4ade80]/30 to-transparent" />

              <StepCard
                step="01"
                title="Вставьте адрес"
                description="Контракт из любой поддерживаемой сети. Код подтянется автоматически через Explorer API."
                delay="0ms"
              />
              <StepCard
                step="02"
                title="AI анализирует"
                description="Статика + LLM-агенты + on-chain обогащение. Параллельно, за 30-90 секунд."
                delay="150ms"
              />
              <StepCard
                step="03"
                title="Получите отчёт"
                description="Структурированный список уязвимостей с severity, рекомендациями и Foundry PoC."
                delay="300ms"
              />
            </div>
          </section>

          {/* ─── Supported Networks ─── */}
          <section className="max-w-3xl mx-auto mb-32 text-center">
            <h2 className="text-xl font-bold text-[#d4ffd4] mb-8">
              Поддерживаемые сети
            </h2>
            <div className="flex flex-wrap justify-center gap-4">
              <NetworkBadge name="Ethereum" />
              <NetworkBadge name="Base" />
              <NetworkBadge name="Arbitrum" />
              <NetworkBadge name="BSC" />
              <NetworkBadge name="Solana" />
            </div>
          </section>

          {/* ─── CTA Section ─── */}
          <section className="max-w-2xl mx-auto text-center mb-24">
            <div className="glass-card glow-border p-12">
              <h2 className="text-3xl md:text-4xl font-bold text-[#d4ffd4] mb-4">
                Готовы проверить контракт?
              </h2>
              <p className="text-[#8bb88b] mb-8">
                Первый аудит бесплатно. Результат через минуту.
              </p>
              <a
                href="https://t.me/KitronBot"
                className="inline-flex items-center gap-2 px-8 py-4 bg-[#4ade80] text-[#0a0e0a] font-bold rounded-xl text-lg hover:bg-[#6ee7a0] transition-all hover:scale-105"
              >
                Попробовать бесплатно
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </a>
            </div>
          </section>
        </div>
      </main>

      {/* ─── Footer ─── */}
      <footer className="border-t border-[rgba(74,222,128,0.08)] px-6 py-8">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-[#547654]">
          <span>2026 wr3. Результаты AI-аудита -- best-effort. Не замена ручному ревью.</span>
          <div className="flex gap-6">
            <Link href="/legal/tos" className="hover:text-[#8bb88b] transition-colors">Условия</Link>
            <Link href="/legal/privacy" className="hover:text-[#8bb88b] transition-colors">Приватность</Link>
            <a href="https://github.com/StarDust1508/WR3" className="hover:text-[#8bb88b] transition-colors">GitHub</a>
          </div>
        </div>
      </footer>
    </>
  );
}

/* ─── Sub-components ─── */

function StatCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="text-center">
      <p className="text-[#547654] text-[10px] uppercase tracking-widest mb-1">{label}</p>
      <p
        className="text-3xl font-extrabold tracking-tight"
        style={{ color: accent ?? "#d4ffd4" }}
      >
        {value}
      </p>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
  delay,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  delay: string;
}) {
  return (
    <div
      className="glass-card hover-lift p-6 animate-fade-in-up"
      style={{ animationDelay: delay }}
    >
      <div className="w-10 h-10 rounded-lg bg-[rgba(74,222,128,0.1)] flex items-center justify-center mb-4 text-[#4ade80]">
        {icon}
      </div>
      <h3 className="text-[#d4ffd4] font-semibold text-sm mb-2">{title}</h3>
      <p className="text-[#8bb88b] text-xs leading-relaxed">{description}</p>
    </div>
  );
}

function StepCard({
  step,
  title,
  description,
  delay,
}: {
  step: string;
  title: string;
  description: string;
  delay: string;
}) {
  return (
    <div className="text-center animate-fade-in-up" style={{ animationDelay: delay }}>
      <div className="w-14 h-14 mx-auto mb-5 rounded-full border border-[rgba(74,222,128,0.3)] bg-[rgba(74,222,128,0.05)] flex items-center justify-center">
        <span className="font-mono text-[#4ade80] text-sm font-bold">{step}</span>
      </div>
      <h3 className="text-[#d4ffd4] font-semibold mb-2">{title}</h3>
      <p className="text-[#8bb88b] text-xs leading-relaxed max-w-[240px] mx-auto">{description}</p>
    </div>
  );
}

function NetworkBadge({ name }: { name: string }) {
  return (
    <div className="glass-card px-5 py-2.5 flex items-center gap-2 hover-lift">
      <div className="w-2 h-2 rounded-full bg-[#4ade80]" />
      <span className="text-sm text-[#c4f0c4] font-medium">{name}</span>
    </div>
  );
}

/* ─── Inline SVG Icons ─── */

function ShieldIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
    </svg>
  );
}

function BrainIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  );
}

function GlobeIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
    </svg>
  );
}
