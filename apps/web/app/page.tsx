import Link from "next/link";
import { ScanInput } from "@/components/scan-input";

const BG = "#0a0e0a";
const FG = "#a8e6a8";
const PRIMARY = "#4ade80";
const MUTED = "#5a8a5a";
const DIM = "#3a5e3a";

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
          <nav style={{ display: "flex", gap: 18, fontSize: 12, alignItems: "center" }}>
            <Link href="/leaderboard" style={{ color: MUTED, textDecoration: "none" }}>leaderboard</Link>
            <Link href="/pricing" style={{ color: MUTED, textDecoration: "none" }}>pricing</Link>
            <Link href="/docs" style={{ color: MUTED, textDecoration: "none" }}>docs</Link>
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
              open bot
            </a>
          </nav>
        </header>

        <section style={{ maxWidth: 720 }}>
          <p style={{ color: MUTED, fontSize: 12, marginBottom: 8 }}>
            // ai-powered smart-contract audit for vibe-coders
          </p>
          <h1
            style={{
              fontSize: "clamp(28px, 5vw, 44px)",
              fontWeight: 700,
              lineHeight: 1.1,
              margin: 0,
              color: FG,
              letterSpacing: "-0.02em",
            }}
          >
            <span style={{ color: PRIMARY }}>$ </span>wr3 audit &lt;contract&gt;
          </h1>
          <p style={{ color: MUTED, fontSize: 14, lineHeight: 1.6, marginTop: 16, maxWidth: 580 }}>
            Score 0-100 across 5 axes. Baseline static + multi-agent LLM triage +
            Foundry PoC retry-loop + AI-fuzzing. EVM (eth / base / arbitrum / bsc)
            and Solana via Sealevel-attacks.
          </p>

          <div style={{ marginTop: 32 }}>
            <ScanInput />
          </div>

          <p style={{ color: DIM, fontSize: 11, marginTop: 12 }}>
            // free tier: 1 contract / 24h. Paid from $29/mo for unlimited scans + full Foundry PoCs.
            <Link href="/pricing" style={{ color: MUTED, textDecoration: "underline", marginLeft: 6 }}>
              pricing →
            </Link>
          </p>
        </section>

        <section
          style={{
            marginTop: 80,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 16,
          }}
        >
          <Feature
            title="multi-engine consensus"
            body="Aderyn + Wake + Slither + Medusa + ItyFuzz + Trident. One pipeline, cross-checked findings."
          />
          <Feature
            title="transparent scoring"
            body="0-100 across 5 axes with published weights. No black-box, no pay-to-play."
          />
          <Feature
            title="solana, first-class"
            body="Sealevel-attacks taxonomy, Trident fuzzer. Most AI auditors skip Solana — we don't."
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
              <Link href="/legal/tos" style={{ color: DIM, textDecoration: "none" }}>terms</Link>
              <Link href="/legal/privacy" style={{ color: DIM, textDecoration: "none" }}>privacy</Link>
              <a href="https://github.com/StarDust1508/WR3" style={{ color: DIM, textDecoration: "none" }}>github</a>
            </div>
          </div>
          <p style={{ marginTop: 16, maxWidth: 720, fontSize: 10 }}>
            AI-assisted audit results are best-effort and not a replacement for human review.
            wr3 provides no warranty. Liability is capped at the cost of the audit.
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
        padding: 16,
      }}
    >
      <h3
        style={{
          color: PRIMARY,
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          margin: 0,
        }}
      >
        // {title}
      </h3>
      <p style={{ color: MUTED, fontSize: 12, marginTop: 8, lineHeight: 1.6 }}>{body}</p>
    </div>
  );
}
