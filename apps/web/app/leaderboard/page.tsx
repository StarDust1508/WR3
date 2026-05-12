import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — leaderboard" };

export default function LeaderboardPage() {
  return (
    <TerminalPageShell title="leaderboard">
      <p style={{ color: "#a8e6a8" }}>
        Public leaderboard of contracts wr3 has audited. Sorted by score, then by date.
      </p>
      <p style={{ color: "#5a8a5a", marginTop: 16 }}>
        // not yet live — coming after the public beta launch.
      </p>
      <p style={{ color: "#5a8a5a", marginTop: 8 }}>
        Until then, scans are private to whoever ran them. Run a scan via{" "}
        <a href="https://t.me/KitronBot" style={{ color: "#4ade80" }}>@KitronBot</a>.
      </p>
    </TerminalPageShell>
  );
}
