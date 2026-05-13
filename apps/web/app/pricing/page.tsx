import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — тарифы" };

const PRIMARY = "#4ade80";
const HI = "#d4ffd4";
const MUTED = "#8bb88b";
const DIM = "#547654";
const BG = "#0a0e0a";

// Deep-link to the Telegram bot — `upgrade_<plan>` payload triggers the
// Stars invoice flow on /start with that arg.
function tgUpgradeLink(plan: string): string {
  return `https://t.me/KitronBot?start=upgrade_${plan}`;
}

export default function PricingPage() {
  return (
    <TerminalPageShell title="Тарифы" eyebrow="// pricing">
      <p style={{ color: MUTED, fontSize: 14, lineHeight: 1.6 }}>
        Платные тарифы — Telegram Stars прямо в боте. Без карт и KYC. Free
        навсегда.
      </p>

      <div
        style={{
          marginTop: 28,
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: 16,
        }}
      >
        <Plan
          name="Free"
          price="$0"
          period="навсегда"
          plan="free"
          ctaLabel="Начать"
          features={[
            "1 контракт в сутки",
            "Baseline-статика (EVM и Solana)",
            "Single-call LLM-триаж",
            "Публичная оценка 0–100 + светофор",
          ]}
        />
        <Plan
          name="Hobby"
          price="$29"
          period="/ мес"
          plan="hobby"
          ctaLabel="Подписаться"
          features={[
            "10 контрактов в месяц",
            "Multi-agent триаж (4 Claude-агента)",
            "Foundry PoC retry-loop для HIGH/CRITICAL",
            "Telegram-уведомления о завершении",
          ]}
        />
        <Plan
          name="Team"
          price="$99"
          period="/ мес"
          plan="team"
          highlighted
          ctaLabel="Подписаться"
          features={[
            "Безлимит контрактов",
            "AI-fuzzing (forge invariant)",
            "Мониторинг каждые 6 часов",
            "Уведомления об изменениях контракта",
          ]}
        />
        <Plan
          name="Pro"
          price="$499"
          period="/ мес"
          plan="pro"
          ctaLabel="Подписаться"
          features={[
            "Всё из Team",
            "Расширенный LLM-триаж (бóльшие контексты)",
            "Кастомные инварианты по запросу",
            "Помощь с Safe Harbor onboarding",
          ]}
        />
      </div>

      <section style={{ marginTop: 48 }}>
        <h2
          style={{
            color: HI,
            fontSize: 18,
            margin: 0,
            fontWeight: 700,
            letterSpacing: "-0.01em",
          }}
        >
          Оплата
        </h2>
        <ul
          style={{
            color: MUTED,
            fontSize: 14,
            lineHeight: 1.7,
            marginTop: 12,
            paddingLeft: 20,
          }}
        >
          <li>
            <span style={{ color: HI, fontWeight: 600 }}>Telegram Stars.</span>{" "}
            Единственный способ оплаты на старте. Hobby — 2200 ⭐, Team — 7500 ⭐,
            Pro — 38 000 ⭐. Период — 30 дней, продление новой покупкой.
          </li>
          <li>
            <span style={{ color: HI, fontWeight: 600 }}>Возврат.</span> Команда{" "}
            <code>/refund</code> в @KitronBot — Telegram возвращает Stars на
            ваш баланс мгновенно. Тариф откатывается к free.
          </li>
        </ul>
      </section>

      <section style={{ marginTop: 40 }}>
        <h2
          style={{
            color: HI,
            fontSize: 18,
            margin: 0,
            fontWeight: 700,
            letterSpacing: "-0.01em",
          }}
        >
          Enterprise и кастом
        </h2>
        <p style={{ color: MUTED, fontSize: 14, marginTop: 10, lineHeight: 1.6 }}>
          Per-engagement аудит, white-label или объёмные скидки — обсудим
          индивидуально.
        </p>
        <a href="https://t.me/KitronBot?start=upgrade_enterprise" style={cta()}>
          Написать в Telegram
        </a>
      </section>
    </TerminalPageShell>
  );

  function cta(): React.CSSProperties {
    return {
      display: "inline-block",
      marginTop: 14,
      color: PRIMARY,
      border: `1px solid ${PRIMARY}`,
      padding: "10px 18px",
      borderRadius: 4,
      textDecoration: "none",
      fontSize: 13,
      fontWeight: 700,
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
        borderRadius: 8,
        padding: 22,
        background: highlighted ? "rgba(74, 222, 128, 0.05)" : BG,
        display: "flex",
        flexDirection: "column",
        gap: 14,
        transition: "border-color 150ms ease, transform 150ms ease",
        position: "relative",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span style={{ color: HI, fontWeight: 700, fontSize: 16 }}>{name}</span>
        {highlighted && (
          <span
            style={{
              color: BG,
              background: PRIMARY,
              fontSize: 10,
              padding: "3px 8px",
              borderRadius: 3,
              fontWeight: 700,
              letterSpacing: "0.04em",
              textTransform: "uppercase",
            }}
          >
            Рекомендуем
          </span>
        )}
      </div>

      <div>
        <span
          style={{
            color: HI,
            fontSize: 30,
            fontWeight: 800,
            lineHeight: 1,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {price}
        </span>
        <span style={{ color: MUTED, fontSize: 12, marginLeft: 6 }}>{period}</span>
      </div>

      <ul
        style={{
          listStyle: "none",
          padding: 0,
          margin: 0,
          fontSize: 13,
          color: MUTED,
          lineHeight: 1.55,
        }}
      >
        {features.map((f) => (
          <li
            key={f}
            style={{ padding: "4px 0", display: "flex", gap: 8, alignItems: "start" }}
          >
            <span style={{ color: PRIMARY, flexShrink: 0 }}>+</span>
            <span>{f}</span>
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
          padding: "11px 16px",
          borderRadius: 4,
          fontSize: 13,
          fontWeight: 700,
        }}
      >
        {ctaLabel}
      </a>
    </article>
  );
}
