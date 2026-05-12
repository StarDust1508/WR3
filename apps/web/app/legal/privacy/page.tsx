import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — privacy" };

export default function PrivacyPage() {
  return (
    <TerminalPageShell title="privacy">
      <p style={{ color: "#a8e6a8", fontSize: 12 }}>// last updated: May 2026</p>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ what we store</h2>
      <ul>
        <li>Your Telegram user id, username, and display name — to attribute scans to you.</li>
        <li>Scan inputs (addresses, optionally pasted source) — to run the pipeline.</li>
        <li>Scan results (findings, scores) — to show them to you and to you alone, unless you opt-in to a public leaderboard.</li>
      </ul>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ third parties</h2>
      <ul>
        <li>
          <b style={{ color: "#a8e6a8" }}>api.navy</b> — runs the LLM calls
          for triage / PoC / fuzzing. NavyAI is a reseller proxy; their
          retention policy is not confirmed as zero. We do not send raw
          0-day exploits through it.
        </li>
        <li>
          <b style={{ color: "#a8e6a8" }}>Etherscan V2</b> — we fetch
          verified contract source from their public API.
        </li>
        <li>
          <b style={{ color: "#a8e6a8" }}>Cloudflare</b> — hosts the Mini App.
        </li>
      </ul>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ data deletion</h2>
      <p>
        DM <a href="https://t.me/KitronBot" style={{ color: "#4ade80" }}>@KitronBot</a> with
        the word <code>delete</code> and we&apos;ll wipe your account + all
        attributed scans within 72 hours.
      </p>
    </TerminalPageShell>
  );
}
