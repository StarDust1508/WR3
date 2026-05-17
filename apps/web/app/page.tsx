import Link from "next/link";
import { ScanInput } from "@/components/scan-input";

const BG = "#0a0e0a";
const FG = "#a8e6a8";
const PRIMARY = "#4ade80";
const HI = "#d4ffd4";
// Lighter green for body / muted copy — contrast ~5.2:1 vs BG (was 3.4:1).
const MUTED = "#8bb88b";
const DIM = "#547654";

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
      next: { revalidate: 60 }, // 1-minute ISR cache
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
    <main
      style={{
        minHeight: "100vh",
        // Background now comes from globals.css — radial gradient + scanlines
        // baked into <body>. Page is transparent so the gradient shows through.
        color: FG,
        // Body switches to sans (set in globals.css). Mono is reserved for
        // <code> and the small terminal-accent chips in header/eyebrow.
        padding: "32px 24px 64px",
      }}
    >
      <div style={{ margin: "0 auto", maxWidth: 980 }}>
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 56,
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <Link
            href="/"
            style={{
              color: PRIMARY,
              fontWeight: 700,
              fontSize: 16,
              border: `1px solid ${PRIMARY}`,
              padding: "5px 10px",
              borderRadius: 4,
              textDecoration: "none",
              fontFamily: "var(--font-mono)",
              boxShadow: "0 0 0 0 rgba(74,222,128,0)",
              transition: "box-shadow 200ms ease",
            }}
          >
            wr3
          </Link>
          <nav style={{ display: "flex", gap: 20, fontSize: 13, alignItems: "center" }}>
            <Link href="/incidents" style={{ color: MUTED, textDecoration: "none" }}>Инциденты</Link>
            <Link href="/leaderboard" style={{ color: MUTED, textDecoration: "none" }}>Лидерборд</Link>
            <Link href="/pricing" style={{ color: MUTED, textDecoration: "none" }}>Тарифы</Link>
            <Link href="/docs" style={{ color: MUTED, textDecoration: "none" }}>Документация</Link>
            <a
              href="https://t.me/KitronBot"
              style={{
                color: BG,
                background: PRIMARY,
                padding: "6px 12px",
                borderRadius: 4,
                textDecoration: "none",
                fontSize: 11,
                fontWeight: 700,
              }}
            >
              Открыть бот
            </a>
          </nav>
        </header>

        <section style={{ maxWidth: 740 }}>
          <p
            className="tg-hint-code"
            style={{
              color: DIM,
              fontSize: 12,
              marginBottom: 12,
              textTransform: "uppercase",
              letterSpacing: "0.1em",
            }}
          >
            AI-аудит смарт-контрактов
          </p>
          <h1
            style={{
              fontSize: "clamp(32px, 5.5vw, 52px)",
              fontWeight: 800,
              lineHeight: 1.05,
              margin: 0,
              color: HI,
              letterSpacing: "-0.02em",
            }}
          >
            Найдите уязвимости до того,
            <br />
            как их найдёт{" "}
            <span style={{ color: PRIMARY }}>атакующий</span>.
          </h1>
          <p
            style={{
              color: MUTED,
              fontSize: 15,
              lineHeight: 1.6,
              marginTop: 20,
              maxWidth: 620,
            }}
          >
            От адреса контракта до полного отчёта за минуту. Multi-engine статика
            (Aderyn, Slither, Wake), LLM-триаж в 4 параллельных агента, Foundry
            PoC retry-loop и AI-fuzzing. EVM и Solana — в одном пайплайне.
          </p>

          <div style={{ marginTop: 32 }}>
            <ScanInput />
          </div>

          <p style={{ color: DIM, fontSize: 12, marginTop: 16 }}>
            Free — 1 контракт в сутки. Платно от $29 в месяц: безлимит и полный
            Foundry PoC.{" "}
            <Link
              href="/pricing"
              style={{ color: PRIMARY, textDecoration: "underline", textUnderlineOffset: 2 }}
            >
              Тарифы
            </Link>
          </p>
        </section>

        {/* Live metrics strip — pulled from /v1/public/stats, ISR-cached
            for a minute. Pure SSR, no client-side fetch jank. */}
        {stats && (
          <section
            style={{
              marginTop: 56,
              padding: "16px 20px",
              background: "rgba(15, 26, 15, 0.6)",
              backdropFilter: "blur(10px)",
              border: `1px solid ${DIM}`,
              borderRadius: 8,
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: 24,
            }}
          >
            <Stat label="Сканов завершено" value={String(stats.total_scans)} />
            <Stat
              label="Средний score"
              value={stats.avg_score != null ? stats.avg_score.toFixed(1) : "—"}
            />
            <Stat
              label="Critical"
              value={String(stats.critical_findings)}
              accent="#f87171"
            />
            <Stat
              label="High"
              value={String(stats.high_findings)}
              accent="#fbbf24"
            />
            <Stat label="Сетей" value={String(stats.networks_count)} />
          </section>
        )}

        <section
          style={{
            marginTop: 96,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: 20,
          }}
        >
          <Feature
            badge="03"
            title="Multi-engine консенсус"
            body="Aderyn, Slither, Wake и собственный baseline-анализатор работают параллельно. Находки, попадающие в несколько движков, получают больший вес на триаже."
          />
          <Feature
            badge="05"
            title="Прозрачная оценка"
            body="Шкала 0–100 по 5 осям с открытыми весами. Никаких чёрных ящиков и pay-to-play — методология опубликована в репозитории."
          />
          <Feature
            badge="13"
            title="Solana — первого класса"
            body="Полная таксономия Sealevel-attacks, метаданные программы через JSON-RPC. Большинство AI-аудиторов пропускают Solana — wr3 нет."
          />
        </section>

        <footer
          style={{
            marginTop: 120,
            paddingTop: 24,
            borderTop: `1px solid ${DIM}`,
            fontSize: 11,
            color: DIM,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 8,
            }}
          >
            <span>© 2026 wr3</span>
            <div style={{ display: "flex", gap: 16 }}>
              <Link href="/legal/tos" style={{ color: MUTED, textDecoration: "none" }}>Условия</Link>
              <Link href="/legal/privacy" style={{ color: MUTED, textDecoration: "none" }}>Приватность</Link>
              <a href="https://github.com/StarDust1508/WR3" style={{ color: MUTED, textDecoration: "none" }}>GitHub</a>
            </div>
          </div>
          <p style={{ marginTop: 16, maxWidth: 720, fontSize: 11, lineHeight: 1.6 }}>
            Результаты AI-аудита — best-effort. Не замена ручному ревью.
            Ответственность ограничена стоимостью аудита.
          </p>
        </footer>
      </div>
    </main>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div>
      <p
        style={{
          color: MUTED,
          fontSize: 11,
          margin: 0,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </p>
      <p
        style={{
          color: accent ?? HI,
          fontSize: 28,
          fontWeight: 800,
          margin: "6px 0 0",
          lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
          letterSpacing: "-0.02em",
        }}
      >
        {value}
      </p>
    </div>
  );
}

function Feature({
  title,
  body,
  badge,
}: {
  title: string;
  body: string;
  badge?: string;
}) {
  return (
    <div
      style={{
        background:
          "linear-gradient(180deg, rgba(15,26,15,0.95) 0%, rgba(15,26,15,0.7) 100%)",
        border: `1px solid ${DIM}`,
        borderRadius: 10,
        padding: 24,
        position: "relative",
        overflow: "hidden",
      }}
    >
      {badge && (
        <span
          style={{
            position: "absolute",
            top: 16,
            right: 16,
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: DIM,
            letterSpacing: "0.08em",
          }}
        >
          //  {badge}
        </span>
      )}
      <h3
        style={{
          color: HI,
          fontSize: 16,
          fontWeight: 700,
          margin: 0,
          letterSpacing: "-0.015em",
        }}
      >
        {title}
      </h3>
      <p style={{ color: MUTED, fontSize: 13.5, marginTop: 12, lineHeight: 1.65 }}>
        {body}
      </p>
    </div>
  );
}
