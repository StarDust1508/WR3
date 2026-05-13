import Link from "next/link";
import type { ReactNode } from "react";

const BG = "#0a0e0a";
const FG = "#a8e6a8";
const HI = "#d4ffd4";
const PRIMARY = "#4ade80";
// MUTED bumped from #5a8a5a → #8bb88b for WCAG AA at small sizes.
const MUTED = "#8bb88b";
const DIM = "#547654";

/**
 * Shared shell for non-Mini-App pages (landing, pricing, docs, legal).
 * Keeps the same brand aesthetic as /tg without re-implementing the
 * navigation on each page.
 *
 * Design rules baked in:
 *   - Body / article copy is in a proportional UI font, not monospace.
 *     Monospace stays only on inline `<code>` and `<pre>`. Wall-of-mono
 *     prose was the biggest readability hit in the previous pass.
 *   - One `$ ` accent per page, on the H1. Subsection titles inside
 *     `{children}` should NOT add their own `$ `.
 *   - One `//` line above the H1 if useful — pages can pass `eyebrow`.
 *     Default: omit the comment line entirely.
 */
export function TerminalPageShell({
  title,
  eyebrow,
  children,
}: {
  title: string;
  /** Optional small uppercase pre-headline shown above the H1. */
  eyebrow?: string;
  children: ReactNode;
}) {
  return (
    <main
      style={{
        minHeight: "100vh",
        background: BG,
        color: FG,
        fontFamily:
          'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Inter, sans-serif',
        padding: "32px 24px 64px",
      }}
    >
      <div style={{ margin: "0 auto", maxWidth: 880 }}>
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 48,
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
              fontFamily:
                'ui-monospace, "SF Mono", Menlo, "JetBrains Mono", Consolas, monospace',
            }}
          >
            wr3
          </Link>
          <nav style={{ display: "flex", gap: 20, fontSize: 13, alignItems: "center" }}>
            <Link href="/incidents" style={{ color: MUTED, textDecoration: "none" }}>
              Инциденты
            </Link>
            <Link href="/leaderboard" style={{ color: MUTED, textDecoration: "none" }}>
              Лидерборд
            </Link>
            <Link href="/pricing" style={{ color: MUTED, textDecoration: "none" }}>
              Тарифы
            </Link>
            <Link href="/docs" style={{ color: MUTED, textDecoration: "none" }}>
              Документация
            </Link>
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

        {eyebrow && (
          <p
            style={{
              color: DIM,
              fontSize: 12,
              margin: "0 0 10px",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              fontFamily:
                'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
            }}
          >
            {eyebrow}
          </p>
        )}
        <h1
          style={{
            fontSize: "clamp(28px, 4.5vw, 40px)",
            fontWeight: 800,
            lineHeight: 1.15,
            margin: "0 0 32px",
            color: HI,
            letterSpacing: "-0.02em",
          }}
        >
          {title}
        </h1>

        <article
          style={{
            background: "#0f1a0f",
            border: `1px solid ${DIM}`,
            borderRadius: 8,
            padding: 28,
            color: FG,
            fontSize: 14,
            lineHeight: 1.7,
          }}
        >
          {children}
        </article>

        <footer
          style={{ marginTop: 64, fontSize: 12, color: MUTED, textAlign: "center" }}
        >
          <Link href="/" style={{ color: MUTED, textDecoration: "none" }}>
            ‹ На главную
          </Link>
        </footer>
      </div>
    </main>
  );
}
