import Link from "next/link";
import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — sign in" };

const PRIMARY = "#4ade80";
const HI = "#d4ffd4";
const MUTED = "#5a8a5a";
const DIM = "#3a5e3a";
const FG = "#a8e6a8";
const BG = "#0a0e0a";

export default function SignInPage() {
  return (
    <TerminalPageShell title="sign in">
      <p style={{ color: MUTED, fontSize: 12 }}>
        // wr3 authenticates via Telegram. SIWE and email are on the roadmap.
      </p>

      <section
        style={{
          marginTop: 24,
          padding: 20,
          background: BG,
          border: `1px solid ${DIM}`,
          borderRadius: 6,
        }}
      >
        <h2 style={{ color: PRIMARY, fontSize: 13, margin: 0, fontWeight: 700 }}>
          $ telegram (active)
        </h2>
        <p style={{ color: FG, fontSize: 13, marginTop: 12, lineHeight: 1.7 }}>
          One-tap. Telegram signs an <code>initData</code> blob with the bot
          token. Backend verifies HMAC, issues a JWT. No password, no email.
        </p>

        <ol style={{ color: FG, fontSize: 12, lineHeight: 1.8, paddingLeft: 20, marginTop: 12 }}>
          <li>Tap the button below to open @KitronBot.</li>
          <li>Press <code>Start</code> in Telegram.</li>
          <li>Tap <code>wr3 audit</code> menu button at the bottom of the chat.</li>
          <li>You&apos;re signed in.</li>
        </ol>

        <a
          href="https://t.me/KitronBot"
          style={{
            display: "inline-block",
            marginTop: 16,
            background: PRIMARY,
            color: BG,
            border: `1px solid ${PRIMARY}`,
            padding: "12px 20px",
            borderRadius: 4,
            textDecoration: "none",
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          $ open @KitronBot →
        </a>

        <p style={{ color: DIM, fontSize: 10, marginTop: 12 }}>
          // already in @KitronBot? Just tap <code>wr3 audit</code> — no need to come back here.
        </p>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ color: HI, fontSize: 12, margin: 0, fontWeight: 700 }}>
          $ siwe (sign-in with ethereum)
          <span
            style={{
              color: MUTED,
              fontSize: 10,
              fontWeight: 400,
              marginLeft: 8,
              letterSpacing: 0,
              textTransform: "none",
            }}
          >
            // roadmap
          </span>
        </h2>
        <p style={{ color: MUTED, fontSize: 12, marginTop: 8 }}>
          For wallet-native devs. Sign a structured message with MetaMask /
          Rabby / Ledger; backend recovers the EOA address and binds it to a
          wr3 account. Not wired up yet — coming with the public beta.
        </p>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ color: HI, fontSize: 12, margin: 0, fontWeight: 700 }}>
          $ email
          <span
            style={{
              color: MUTED,
              fontSize: 10,
              fontWeight: 400,
              marginLeft: 8,
              letterSpacing: 0,
              textTransform: "none",
            }}
          >
            // roadmap
          </span>
        </h2>
        <p style={{ color: MUTED, fontSize: 12, marginTop: 8 }}>
          Magic-link via Resend. For org accounts that can&apos;t hand out wallet
          seeds. Roadmap.
        </p>
      </section>

      <p style={{ color: DIM, fontSize: 11, marginTop: 32 }}>
        // already signed in? Open the Mini App directly:{" "}
        <Link href="/tg" style={{ color: PRIMARY }}>/tg</Link>
      </p>
    </TerminalPageShell>
  );
}
