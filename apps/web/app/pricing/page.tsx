import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — pricing" };

const PRIMARY = "#4ade80";
const HI = "#d4ffd4";
const MUTED = "#5a8a5a";
const DIM = "#3a5e3a";
const BG = "#0a0e0a";

// Deep-link to the Telegram bot with a payload that tells the bot which
// plan the user wants. The bot handler interprets the start param.
function tgUpgradeLink(plan: string): string {
  return `https://t.me/KitronBot?start=upgrade_${plan}`;
}

export default function PricingPage() {
  return (
    <TerminalPageShell title="pricing">
      <p style={{ color: MUTED, fontSize: 12 }}>
        // free forever. paid plans start when the public beta opens.
        click <code>$ subscribe</code> to ping @KitronBot with your plan choice.
      </p>

      <div
        style={{
          marginTop: 24,
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: 16,
        }}
      >
        <Plan
          name="free"
          price="$0"
          period="forever"
          plan="free"
          features={[
            "1 contract / 24h",
            "Baseline static analysis (EVM + Solana)",
            "Single-call LLM triage",
            "Public score 0-100, traffic light",
          ]}
        />
        <Plan
          name="hobby"
          price="$29"
          period="/ month"
          plan="hobby"
          features={[
            "10 contracts / month",
            "Multi-agent triage (4 parallel Claude)",
            "Foundry PoC retry-loop (HIGH/CRITICAL)",
            "Telegram alerts on completion",
          ]}
        />
        <Plan
          name="team"
          price="$99"
          period="/ month"
          plan="team"
          highlighted
          features={[
            "Unlimited contracts",
            "AI-fuzzing (medusa / forge invariant)",
            "Continuous monitoring (24/7)",
            "Slack / Discord webhooks",
          ]}
        />
        <Plan
          name="pro"
          price="$499"
          period="/ month"
          plan="pro"
          features={[
            "Everything in team",
            "Certora Prover (formal verification)",
            "Custom invariants on request",
            "Safe Harbor onboarding helper",
          ]}
        />
      </div>

      <section style={{ marginTop: 40 }}>
        <h2
          style={{
            color: PRIMARY,
            fontSize: 13,
            margin: 0,
            fontWeight: 700,
          }}
        >
          $ payment
        </h2>
        <ul style={{ color: MUTED, fontSize: 12, lineHeight: 1.8, marginTop: 8 }}>
          <li>
            <span style={{ color: HI }}>crypto.</span> USDC on base / arbitrum,
            or TON. Pay via @KitronBot using your wallet. <i style={{ color: MUTED }}>(integration in roadmap)</i>
          </li>
          <li>
            <span style={{ color: HI }}>fiat.</span> Stripe / Polar. <i style={{ color: MUTED }}>(after public beta)</i>
          </li>
          <li>
            <span style={{ color: HI }}>refund.</span> First month of any paid plan refundable in full, no questions.
          </li>
        </ul>
      </section>

      <section style={{ marginTop: 32 }}>
        <h2 style={{ color: PRIMARY, fontSize: 13, margin: 0, fontWeight: 700 }}>
          $ enterprise / custom
        </h2>
        <p style={{ color: MUTED, fontSize: 12, marginTop: 8 }}>
          // need a per-engagement audit, white-label, or volume discounts?
        </p>
        <a
          href="https://t.me/KitronBot?start=upgrade_enterprise"
          style={cta()}
        >
          $ contact via @KitronBot
        </a>
      </section>
    </TerminalPageShell>
  );

  function cta(): React.CSSProperties {
    return {
      display: "inline-block",
      marginTop: 8,
      color: PRIMARY,
      border: `1px solid ${PRIMARY}`,
      padding: "8px 14px",
      borderRadius: 4,
      textDecoration: "none",
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: "0.04em",
      textTransform: "uppercase",
    };
  }
}

function Plan({
  name,
  price,
  period,
  plan,
  features,
  highlighted,
}: {
  name: string;
  price: string;
  period: string;
  plan: string;
  features: string[];
  highlighted?: boolean;
}) {
  return (
    <article
      style={{
        border: `1px solid ${highlighted ? PRIMARY : DIM}`,
        borderRadius: 6,
        padding: 18,
        background: highlighted ? "rgba(74, 222, 128, 0.04)" : BG,
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <span style={{ color: PRIMARY, fontWeight: 700, fontSize: 14 }}>// {name}</span>
        {highlighted && (
          <span
            style={{
              color: BG,
              background: PRIMARY,
              fontSize: 9,
              padding: "2px 6px",
              borderRadius: 3,
              fontWeight: 700,
              letterSpacing: "0.06em",
            }}
          >
            POPULAR
          </span>
        )}
      </div>

      <div>
        <span style={{ color: HI, fontSize: 26, fontWeight: 800, lineHeight: 1 }}>{price}</span>
        <span style={{ color: MUTED, fontSize: 11, marginLeft: 6 }}>{period}</span>
      </div>

      <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 12, color: MUTED }}>
        {features.map((f) => (
          <li key={f} style={{ padding: "3px 0" }}>
            <span style={{ color: PRIMARY, marginRight: 6 }}>+</span>
            {f}
          </li>
        ))}
      </ul>

      <a
        href={tgUpgradeLink(plan)}
        style={{
          marginTop: "auto",
          display: "inline-block",
          textAlign: "center",
          textDecoration: "none",
          background: highlighted ? PRIMARY : "transparent",
          color: highlighted ? BG : PRIMARY,
          border: `1px solid ${PRIMARY}`,
          padding: "10px 14px",
          borderRadius: 4,
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}
      >
        $ {plan === "free" ? "start" : "subscribe"}
      </a>
    </article>
  );
}
