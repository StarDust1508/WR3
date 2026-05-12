import Link from "next/link";
import type { ReactNode } from "react";

const BG = "#0a0e0a";
const FG = "#a8e6a8";
const PRIMARY = "#4ade80";
const MUTED = "#5a8a5a";
const DIM = "#3a5e3a";

/**
 * Shared shell for non-Mini-App pages (landing, pricing, docs, legal).
 * Keeps the same terminal aesthetic as /tg without re-implementing the
 * navigation on each page.
 */
export function TerminalPageShell({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
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
            marginBottom: 40,
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
          <nav style={{ display: "flex", gap: 18, fontSize: 12, alignItems: "center" }}>
            <Link href="/incidents" style={{ color: MUTED, textDecoration: "none" }}>инциденты</Link>
            <Link href="/leaderboard" style={{ color: MUTED, textDecoration: "none" }}>лидерборд</Link>
            <Link href="/pricing" style={{ color: MUTED, textDecoration: "none" }}>тарифы</Link>
            <Link href="/docs" style={{ color: MUTED, textDecoration: "none" }}>доки</Link>
            <a
              href="https://t.me/KitronBot"
              style={{
                color: PRIMARY,
                border: `1px solid ${PRIMARY}`,
                padding: "4px 10px",
                borderRadius: 4,
                textDecoration: "none",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                fontSize: 10,
                fontWeight: 700,
              }}
            >
              открыть бот
            </a>
          </nav>
        </header>

        <p style={{ color: MUTED, fontSize: 12, margin: 0 }}>// {title}</p>
        <h1
          style={{
            fontSize: "clamp(24px, 4vw, 36px)",
            fontWeight: 700,
            lineHeight: 1.15,
            margin: "4px 0 24px",
            color: FG,
            letterSpacing: "-0.02em",
          }}
        >
          <span style={{ color: PRIMARY }}>$ </span>
          wr3 {title}
        </h1>

        <article
          style={{
            background: "#0f1a0f",
            border: `1px solid ${DIM}`,
            borderRadius: 6,
            padding: 24,
            color: FG,
            fontSize: 13,
            lineHeight: 1.7,
          }}
        >
          {children}
        </article>

        <footer style={{ marginTop: 64, fontSize: 11, color: DIM, textAlign: "center" }}>
          <Link href="/" style={{ color: DIM, textDecoration: "none" }}>← на главную</Link>
        </footer>
      </div>
    </main>
  );
}
