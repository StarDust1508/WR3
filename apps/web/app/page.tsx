import Link from "next/link";
import { ScanInput } from "@/components/scan-input";

const BG = "#0a0e0a";
const FG = "#a8e6a8";
const PRIMARY = "#4ade80";
const HI = "#d4ffd4";
// Lighter green for body / muted copy — contrast ~5.2:1 vs BG (was 3.4:1).
const MUTED = "#8bb88b";
const DIM = "#547654";

export default function HomePage() {
  return (
    <main
      style={{
        minHeight: "100vh",
        background: BG,
        color: FG,
        fontFamily:
          'ui-monospace, "SF Mono", Menlo, "JetBrains Mono", Consolas, monospace',
        padding: "32px 24px 64px",
      }}
    >
      <div style={{ margin: "0 auto", maxWidth: 880 }}>
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

        <section
          style={{
            marginTop: 96,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: 16,
          }}
        >
          <Feature
            title="Multi-engine консенсус"
            body="Aderyn, Slither, Wake и собственный baseline-анализатор работают параллельно. Кросс-проверенные находки получают больший вес на триаже."
          />
          <Feature
            title="Прозрачная оценка"
            body="Шкала 0–100 по 5 осям с открытыми весами. Никаких чёрных ящиков, никаких pay-to-play — методология опубликована."
          />
          <Feature
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

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div
      style={{
        background: "#0f1a0f",
        border: `1px solid ${DIM}`,
        borderRadius: 6,
        padding: 20,
        transition: "border-color 150ms ease, transform 150ms ease",
      }}
    >
      <h3
        style={{
          color: HI,
          fontSize: 14,
          fontWeight: 700,
          margin: 0,
          letterSpacing: "-0.01em",
        }}
      >
        {title}
      </h3>
      <p style={{ color: MUTED, fontSize: 13, marginTop: 10, lineHeight: 1.65 }}>{body}</p>
    </div>
  );
}
