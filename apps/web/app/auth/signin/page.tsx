import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — sign in" };

export default function SignInPage() {
  return (
    <TerminalPageShell title="sign in">
      <p style={{ color: "#a8e6a8" }}>
        wr3 currently authenticates exclusively through Telegram.
      </p>
      <p style={{ color: "#5a8a5a", marginTop: 16, fontSize: 12 }}>
        // Open <a href="https://t.me/KitronBot" style={{ color: "#4ade80" }}>@KitronBot</a> →{" "}
        tap <code style={{ color: "#a8e6a8" }}>Start</code> → tap the{" "}
        <code style={{ color: "#a8e6a8" }}>wr3 audit</code> menu button.
      </p>
      <p style={{ color: "#5a8a5a", marginTop: 16, fontSize: 12 }}>
        Wallet sign-in (SIWE) and email magic-link are in the roadmap.
      </p>
    </TerminalPageShell>
  );
}
