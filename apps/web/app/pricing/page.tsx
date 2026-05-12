import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — тарифы" };

const PRIMARY = "#4ade80";
const HI = "#d4ffd4";
const MUTED = "#5a8a5a";
const DIM = "#3a5e3a";
const BG = "#0a0e0a";

// Deep-link в Telegram-бот с payload — бот понимает префикс upgrade_<plan>
// и отвечает блёрбом про конкретный тариф.
function tgUpgradeLink(plan: string): string {
  return `https://t.me/KitronBot?start=upgrade_${plan}`;
}

export default function PricingPage() {
  return (
    <TerminalPageShell title="тарифы">
      <p style={{ color: MUTED, fontSize: 12 }}>
        // free навсегда. Платные тарифы — оплата через{" "}
        <span style={{ color: HI }}>Telegram Stars</span> прямо в боте,
        в один тап. Без карт, без KYC. Нажми <code>$ подписаться</code> ↓
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
          period="навсегда"
          plan="free"
          ctaLabel="старт"
          features={[
            "1 контракт / 24 ч",
            "Baseline-статика (EVM + Solana)",
            "Single-call LLM-триаж",
            "Публичная оценка 0–100 + светофор",
          ]}
        />
        <Plan
          name="hobby"
          price="$29"
          period="/ мес"
          plan="hobby"
          ctaLabel="подписаться"
          features={[
            "10 контрактов / мес",
            "Multi-agent триаж (4 параллельных Claude)",
            "Foundry PoC retry-loop (HIGH/CRITICAL)",
            "Telegram-уведомления о завершении",
          ]}
        />
        <Plan
          name="team"
          price="$99"
          period="/ мес"
          plan="team"
          highlighted
          ctaLabel="подписаться"
          features={[
            "Безлимит контрактов",
            "AI-fuzzing (medusa / forge invariant)",
            "Мониторинг 24/7",
            "Slack / Discord вебхуки",
          ]}
        />
        <Plan
          name="pro"
          price="$499"
          period="/ мес"
          plan="pro"
          ctaLabel="подписаться"
          features={[
            "Всё из team",
            "Certora Prover (formal verification)",
            "Кастомные инварианты по запросу",
            "Помощь с Safe Harbor onboarding",
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
          $ оплата
        </h2>
        <ul style={{ color: MUTED, fontSize: 12, lineHeight: 1.8, marginTop: 8 }}>
          <li>
            <span style={{ color: HI }}>telegram stars.</span> Единственный
            способ оплаты сейчас. В один тап прямо в боте, без карт и KYC.
            Hobby — 2200 ⭐, team — 7500 ⭐, pro — 38000 ⭐. Период 30 дней,
            продление — новой покупкой.
          </li>
          <li>
            <span style={{ color: HI }}>возврат.</span> Команда{" "}
            <code>/refund</code> в @KitronBot — Telegram возвращает Stars на
            твой баланс мгновенно. Тариф откатывается к free.
          </li>
        </ul>
      </section>

      <section style={{ marginTop: 32 }}>
        <h2 style={{ color: PRIMARY, fontSize: 13, margin: 0, fontWeight: 700 }}>
          $ enterprise / кастом
        </h2>
        <p style={{ color: MUTED, fontSize: 12, marginTop: 8 }}>
          // нужен per-engagement аудит, white-label или объёмные скидки?
        </p>
        <a
          href="https://t.me/KitronBot?start=upgrade_enterprise"
          style={cta()}
        >
          $ написать в @KitronBot
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
  ctaLabel,
}: {
  name: string;
  price: string;
  period: string;
  plan: string;
  features: string[];
  highlighted?: boolean;
  ctaLabel: string;
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
            ВЫБОР
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
        $ {ctaLabel}
      </a>
    </article>
  );
}
