import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — terms" };

export default function TosPage() {
  return (
    <TerminalPageShell title="terms of service">
      <p style={{ color: "#a8e6a8", fontSize: 12 }}>
        // last updated: May 2026 · in plain language. The legal version comes
        with the public launch.
      </p>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ what wr3 is</h2>
      <p>wr3 runs an automated, AI-assisted audit pipeline on smart-contract
        source you provide. It produces a score (0-100) and a list of findings.
        It is not a substitute for human review.</p>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ what wr3 is NOT</h2>
      <ul>
        <li>Not an insurer. We don&apos;t cover losses from exploits we miss or misclassify.</li>
        <li>Not financial advice. Score is a signal, not a recommendation.</li>
        <li>Not exhaustive. AI hallucinates; static analyzers miss things; human review still matters.</li>
      </ul>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ liability</h2>
      <p>Liability is capped at the cost of the audit, or $0 for free-tier scans.</p>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ disclosure</h2>
      <p>Severity ratings, scoring weights, and the pipeline source live on{" "}
        <a href="https://github.com/StarDust1508/WR3" style={{ color: "#4ade80" }}>GitHub</a> — verify them.</p>
    </TerminalPageShell>
  );
}
