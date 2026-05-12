import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — docs" };

export default function DocsPage() {
  return (
    <TerminalPageShell title="docs">
      <p>The fastest way to audit a contract is the Telegram bot.</p>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ get started</h2>
      <ol style={{ paddingLeft: 20, color: "#a8e6a8" }}>
        <li>Open <a href="https://t.me/KitronBot" style={{ color: "#4ade80" }}>@KitronBot</a> in Telegram.</li>
        <li>Tap <code>Start</code>, then the <code>wr3 audit</code> menu button.</li>
        <li>Paste a contract address (0x… for EVM, base58 for Solana).</li>
        <li>Pick the network. Tap <code>run</code>.</li>
        <li>Pipeline runs through 7 stages in ~30–60s. You see a score and findings.</li>
      </ol>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ what the pipeline does</h2>
      <pre style={{ background: "#0a0e0a", padding: 12, border: "1px solid #1f3d1f", borderRadius: 4, fontSize: 11, color: "#a8e6a8", overflowX: "auto" }}>
{`stage 1  ingestion       Etherscan V2 / explorer source pull
stage 2  static-analysis  baseline regex + Aderyn + Wake + Slither (EVM)
                          Sealevel-attacks (Solana)
stage 3  ai-triage        4 parallel Claude agents → consensus merge
stage 4  poc-generation   LLM writes Foundry test → forge test retry-loop
stage 5  ai-fuzzing       LLM generates invariants → medusa/forge invariant
stage 6  formal-verif     [premium] Certora Prover
stage 7  scoring          5 axes, 0-100, traffic-light verdict`}
      </pre>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ owner toggles</h2>
      <p>
        In the Mini App, the <code>cfg</code> button opens the Owner panel.
        Each toggle directly changes pipeline behaviour on your next scan:
        <code>auto_poc</code>, <code>auto_fuzzing</code>,{" "}
        <code>multi_agent_triage</code>. Defaults are all-on.
      </p>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ links</h2>
      <ul>
        <li><a href="https://github.com/StarDust1508/WR3" style={{ color: "#4ade80" }}>GitHub repo</a></li>
        <li><a href="https://github.com/coral-xyz/sealevel-attacks" style={{ color: "#4ade80" }}>Sealevel-attacks taxonomy</a></li>
        <li><a href="https://book.getfoundry.sh" style={{ color: "#4ade80" }}>Foundry book</a></li>
      </ul>
    </TerminalPageShell>
  );
}
