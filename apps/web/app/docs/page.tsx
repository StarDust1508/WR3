import Link from "next/link";
import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — docs" };

const PRIMARY = "#4ade80";
const MUTED = "#5a8a5a";
const DIM = "#3a5e3a";
const FG = "#a8e6a8";
const HI = "#d4ffd4";

const codeBlock: React.CSSProperties = {
  background: "#0a0e0a",
  padding: 12,
  border: `1px solid ${DIM}`,
  borderRadius: 4,
  fontSize: 11,
  color: FG,
  overflowX: "auto",
  fontFamily: "inherit",
  marginTop: 8,
};

const h2: React.CSSProperties = {
  color: PRIMARY,
  fontSize: 14,
  marginTop: 32,
  marginBottom: 8,
  fontWeight: 700,
};

const h3: React.CSSProperties = {
  color: HI,
  fontSize: 13,
  marginTop: 20,
  marginBottom: 6,
  fontWeight: 700,
};

const tableBase: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 12,
  marginTop: 8,
};

const td: React.CSSProperties = {
  padding: "6px 10px",
  borderBottom: `1px solid ${DIM}`,
  verticalAlign: "top",
};

export default function DocsPage() {
  return (
    <TerminalPageShell title="docs">
      <nav style={{ color: MUTED, fontSize: 11, marginBottom: 16 }}>
        // contents:{" "}
        <Toc href="#quickstart">quickstart</Toc> ·{" "}
        <Toc href="#pipeline">pipeline</Toc> ·{" "}
        <Toc href="#scoring">scoring</Toc> ·{" "}
        <Toc href="#owner">owner toggles</Toc> ·{" "}
        <Toc href="#api">api</Toc> ·{" "}
        <Toc href="#faq">faq</Toc>
      </nav>

      <h2 id="quickstart" style={h2}>$ quickstart</h2>
      <p>The fastest path to a working audit:</p>
      <ol style={{ paddingLeft: 20, color: FG }}>
        <li>
          Open <a href="https://t.me/KitronBot" style={{ color: PRIMARY }}>@KitronBot</a> in Telegram.
        </li>
        <li>Tap <code>Start</code>, then the <code>wr3 audit</code> menu button.</li>
        <li>Paste a contract address (0x… for EVM, base58 for Solana).</li>
        <li>Pick the chain. Tap <code>run</code>.</li>
        <li>Pipeline runs ~30–60s. You see a score and findings.</li>
      </ol>
      <p style={{ color: MUTED, fontSize: 11 }}>
        // need a contract to test? Try USDC:{" "}
        <code>0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48</code> on ethereum.
      </p>

      <h2 id="pipeline" style={h2}>$ pipeline — 7 stages</h2>
      <p>
        Every scan flows through the same DAG. Stages can be turned off per-user
        via the <Link href="#owner" style={{ color: PRIMARY }}>owner toggles</Link>.
      </p>
      <pre style={codeBlock}>
{`stage 1   ingestion        Etherscan V2 → verified source pull
                            proxy resolution (EIP-1967 implementation)
stage 2   static-analysis   baseline regex + Aderyn + Wake + Slither (EVM)
                            Sealevel-attacks (Solana)
stage 3   ai-triage         4 parallel Claude agents → consensus merge
                              · severity-classifier
                              · false-positive-filter
                              · business-logic-reasoner
                              · cross-contract-analyzer
stage 4   poc-generation    LLM writes Foundry test for HIGH/CRITICAL
                            → forge test --json → retry-loop on failure
                            (max 3 attempts per finding)
stage 5   ai-fuzzing        LLM generates invariant_* functions
                            → medusa fuzz / forge invariant testing
                            → counter-example analyzer: real vs artifact
stage 6   formal-verif      Certora Prover (paid tier only)
stage 7   scoring           5 axes, 0–100, traffic-light verdict`}
      </pre>

      <h3 style={h3}>per-stage cost characteristics</h3>
      <div style={{ overflowX: "auto" }}>
        <table style={tableBase}>
          <thead>
            <tr style={{ color: MUTED, fontSize: 10 }}>
              <th style={{ ...td, textAlign: "left" }}>STAGE</th>
              <th style={{ ...td, textAlign: "left" }}>LLM CALLS</th>
              <th style={{ ...td, textAlign: "left" }}>BINARY</th>
              <th style={{ ...td, textAlign: "left" }}>TIME</th>
            </tr>
          </thead>
          <tbody style={{ color: FG }}>
            <tr><td style={td}>ingestion</td><td style={td}>0</td><td style={td}>—</td><td style={td}>&lt;1s</td></tr>
            <tr><td style={td}>static</td><td style={td}>0</td><td style={td}>aderyn/wake/slither</td><td style={td}>3–15s</td></tr>
            <tr><td style={td}>triage</td><td style={td}>4 parallel</td><td style={td}>—</td><td style={td}>5–20s</td></tr>
            <tr><td style={td}>poc</td><td style={td}>1–3 / finding</td><td style={td}>forge</td><td style={td}>10–60s</td></tr>
            <tr><td style={td}>fuzzing</td><td style={td}>1 (gen) + 1 (analyze)</td><td style={td}>medusa / forge</td><td style={td}>15–120s</td></tr>
            <tr><td style={td}>scoring</td><td style={td}>0</td><td style={td}>—</td><td style={td}>&lt;100ms</td></tr>
          </tbody>
        </table>
      </div>

      <h2 id="scoring" style={h2}>$ scoring — 5 axes</h2>
      <p>
        The final 0–100 score is a weighted average of 5 axes. Weights are{" "}
        <b style={{ color: HI }}>public</b>:
      </p>
      <div style={{ overflowX: "auto" }}>
        <table style={tableBase}>
          <thead>
            <tr style={{ color: MUTED, fontSize: 10 }}>
              <th style={{ ...td, textAlign: "left" }}>AXIS</th>
              <th style={{ ...td, textAlign: "right" }}>WEIGHT</th>
              <th style={{ ...td, textAlign: "left" }}>SIGNAL</th>
            </tr>
          </thead>
          <tbody style={{ color: FG }}>
            <tr><td style={td}>code security</td><td style={{ ...td, textAlign: "right" }}>35%</td><td style={td}>findings (penalty by severity)</td></tr>
            <tr><td style={td}>tokenomics / centralization</td><td style={{ ...td, textAlign: "right" }}>20%</td><td style={td}>owner privileges, mint authority, upgradeability</td></tr>
            <tr><td style={td}>liquidity risk</td><td style={{ ...td, textAlign: "right" }}>15%</td><td style={td}>LP locked %, top-holder concentration</td></tr>
            <tr><td style={td}>team / kyc</td><td style={{ ...td, textAlign: "right" }}>15%</td><td style={td}>verified on explorer, public team, KYC badge</td></tr>
            <tr><td style={td}>on-chain behavior</td><td style={{ ...td, textAlign: "right" }}>15%</td><td style={td}>TVL trend, swap volume, anomaly score, age</td></tr>
          </tbody>
        </table>
      </div>

      <h3 style={h3}>severity → score penalty</h3>
      <pre style={codeBlock}>
{`critical    -40   any single critical forces tier=red
high        -20   caps tier at yellow at best
medium       -7
low          -2
info          0`}
      </pre>

      <h3 style={h3}>tier mapping</h3>
      <pre style={codeBlock}>
{`0  ≤ score < 40    red       high risk    has critical/high or many medium
40 ≤ score < 70    yellow    caution      medium-severity present
70 ≤ score < 90    green     acceptable   only minor issues
90 ≤ score ≤ 100   blue      excellent    no security findings of note`}
      </pre>

      <h2 id="owner" style={h2}>$ owner toggles</h2>
      <p>
        Open the Mini App, tap <code>cfg</code> in the header. Each toggle
        directly changes pipeline behaviour on your next scan:
      </p>
      <div style={{ overflowX: "auto" }}>
        <table style={tableBase}>
          <thead>
            <tr style={{ color: MUTED, fontSize: 10 }}>
              <th style={{ ...td, textAlign: "left" }}>TOGGLE</th>
              <th style={{ ...td, textAlign: "left" }}>EFFECT</th>
            </tr>
          </thead>
          <tbody style={{ color: FG }}>
            <tr><td style={td}><code>auto_poc</code></td><td style={td}>Runs stage 4 (Foundry PoC retry-loop). Default: on.</td></tr>
            <tr><td style={td}><code>auto_fuzzing</code></td><td style={td}>Runs stage 5 (medusa / forge invariant). Default: on.</td></tr>
            <tr><td style={td}><code>multi_agent_triage</code></td><td style={td}>4 parallel Claude agents. Off = single-call triage. Default: on.</td></tr>
            <tr><td style={td}><code>continuous_monitoring</code></td><td style={td}>24/7 re-scan of watched contracts. <i style={{ color: MUTED }}>(roadmap)</i></td></tr>
            <tr><td style={td}><code>anonymous_in_public</code></td><td style={td}>Hide from /leaderboard, scans show as anon. Default: off.</td></tr>
          </tbody>
        </table>
      </div>

      <h2 id="api" style={h2}>$ api</h2>
      <p>Public endpoints (no auth):</p>
      <pre style={codeBlock}>
{`GET  /v1/public/scans?limit=50&min_score=0
GET  /v1/public/stats
GET  /v1/health
GET  /v1/version`}
      </pre>

      <p style={{ marginTop: 16 }}>Authenticated (Bearer JWT from Telegram initData):</p>
      <pre style={codeBlock}>
{`POST   /v1/scan                      { address, network, source_code? } -> { job_id }
GET    /v1/scan/{scan_id}            full scan + findings
GET    /v1/scan/{job_id}/events      SSE stream of pipeline progress
GET    /v1/scan/me                   recent scans owned by current user
GET    /v1/auth/me                   current user
GET    /v1/auth/preferences          owner toggles
PATCH  /v1/auth/preferences          partial update`}
      </pre>

      <h2 id="faq" style={h2}>$ faq</h2>

      <h3 style={h3}>does wr3 audit Solana?</h3>
      <p>
        Yes. We ship our own{" "}
        <a href="https://github.com/coral-xyz/sealevel-attacks" style={{ color: PRIMARY }}>
          Sealevel-attacks
        </a>
        -based analyzer for Anchor programs, covering 11 of 13 categories
        (signer auth, arbitrary CPI, PDA bump from input, etc).
      </p>

      <h3 style={h3}>why a score and not just findings?</h3>
      <p>
        A single number lets non-experts make a go / no-go decision in 2 seconds.
        The breakdown is one tap away. Existing scoring tools (CertiK Skynet) are{" "}
        <b style={{ color: HI }}>pay-to-play</b> with hidden weights — wr3 publishes them.
      </p>

      <h3 style={h3}>can I scan a contract that isn&apos;t verified on Etherscan?</h3>
      <p>
        Paste the source code directly in the scan form. The pipeline runs
        identically whether the source comes from the explorer or from you.
      </p>

      <h3 style={h3}>how do I export findings?</h3>
      <p>
        Currently: copy from the scan detail page or hit{" "}
        <code>GET /v1/scan/{`{id}`}</code> with your token. JSON / Markdown / PDF
        export is on the roadmap.
      </p>

      <h3 style={h3}>how do I delete my data?</h3>
      <p>
        DM <a href="https://t.me/KitronBot" style={{ color: PRIMARY }}>@KitronBot</a>{" "}
        with <code>delete</code>. We wipe your user + all attributed scans within
        72 hours.
      </p>

      <h2 style={h2}>$ links</h2>
      <ul style={{ color: FG }}>
        <li><a href="https://github.com/StarDust1508/WR3" style={{ color: PRIMARY }}>GitHub repo</a></li>
        <li><a href="https://github.com/coral-xyz/sealevel-attacks" style={{ color: PRIMARY }}>Sealevel-attacks taxonomy</a></li>
        <li><a href="https://github.com/Cyfrin/aderyn" style={{ color: PRIMARY }}>Aderyn static analyzer</a></li>
        <li><a href="https://github.com/Ackee-Blockchain/wake" style={{ color: PRIMARY }}>Wake framework</a></li>
        <li><a href="https://github.com/crytic/slither" style={{ color: PRIMARY }}>Slither</a></li>
        <li><a href="https://github.com/crytic/medusa" style={{ color: PRIMARY }}>Medusa fuzzer</a></li>
        <li><a href="https://book.getfoundry.sh" style={{ color: PRIMARY }}>Foundry book</a></li>
      </ul>
    </TerminalPageShell>
  );
}

function Toc({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} style={{ color: PRIMARY, textDecoration: "none" }}>
      {children}
    </a>
  );
}
