import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — pricing" };

const PRIMARY = "#4ade80";
const MUTED = "#5a8a5a";
const DIM = "#3a5e3a";

export default function PricingPage() {
  return (
    <TerminalPageShell title="pricing">
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 16 }}>
        <Plan
          name="free"
          price="$0"
          period="forever"
          features={[
            "1 contract / 24h",
            "Baseline static analysis (EVM + Solana)",
            "Public score 0-100, traffic light",
            "Single-call LLM triage",
          ]}
        />
        <Plan
          name="hobby"
          price="$29"
          period="per month"
          features={[
            "10 contracts / month",
            "Full multi-agent triage (4 parallel Claude agents)",
            "Foundry PoC retry-loop for HIGH/CRITICAL",
            "Telegram alerts",
          ]}
        />
        <Plan
          name="team"
          price="$99"
          period="per month"
          features={[
            "Unlimited contracts",
            "AI-fuzzing (medusa / forge invariant)",
            "Continuous monitoring (24/7)",
            "Slack / Discord webhooks",
          ]}
          highlighted
        />
        <Plan
          name="pro"
          price="$499"
          period="per month"
          features={[
            "Everything in team",
            "Certora Prover (formal verification, premium tier)",
            "Custom invariants on request",
            "Safe Harbor onboarding helper",
          ]}
        />
      </ul>

      <p style={{ color: MUTED, fontSize: 11, marginTop: 24 }}>
        // payments: USDC on base/arbitrum or TON via @KitronBot menu. fiat via Stripe (coming soon).
        first month of any paid plan refundable in full.
      </p>
    </TerminalPageShell>
  );
}

function Plan({
  name,
  price,
  period,
  features,
  highlighted,
}: {
  name: string;
  price: string;
  period: string;
  features: string[];
  highlighted?: boolean;
}) {
  return (
    <li
      style={{
        border: `1px solid ${highlighted ? PRIMARY : DIM}`,
        borderRadius: 6,
        padding: 16,
        background: highlighted ? "rgba(74, 222, 128, 0.04)" : "transparent",
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <span style={{ color: PRIMARY, fontWeight: 700, fontSize: 14 }}>
          // {name}
        </span>
        <span>
          <span style={{ color: "#d4ffd4", fontSize: 18, fontWeight: 700 }}>{price}</span>
          <span style={{ color: MUTED, fontSize: 11, marginLeft: 6 }}>{period}</span>
        </span>
      </div>
      <ul style={{ listStyle: "none", padding: 0, margin: "12px 0 0", fontSize: 12, color: MUTED }}>
        {features.map((f) => (
          <li key={f} style={{ padding: "2px 0" }}>
            <span style={{ color: PRIMARY }}>+ </span>{f}
          </li>
        ))}
      </ul>
    </li>
  );
}
