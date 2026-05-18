import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — тарифы" };

// Deep-link to the Telegram bot — `upgrade_<plan>` payload triggers the
// Stars invoice flow on /start with that arg.
function tgUpgradeLink(plan: string): string {
  return `https://t.me/KitronBot?start=upgrade_${plan}`;
}

export default function PricingPage() {
  return (
    <TerminalPageShell title="Тарифы" eyebrow="// pricing">
      <p className="text-[#8bb88b] text-sm leading-relaxed">
        Платные тарифы — Telegram Stars прямо в боте. Без карт и KYC. Free
        навсегда.
      </p>

      {/* ─── Plan Grid ─── */}
      <div className="mt-7 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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

      {/* ─── Payment Section ─── */}
      <section className="mt-12 glass-card p-6 animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
        <h2 className="text-[#d4ffd4] text-lg font-bold tracking-tight m-0">
          Оплата
        </h2>
        <ul className="text-[#8bb88b] text-sm leading-relaxed mt-3 pl-5 list-disc">
          <li>
            <span className="text-[#d4ffd4] font-semibold">Telegram Stars.</span>{" "}
            Единственный способ оплаты на старте. Hobby — 2200 ⭐, Team — 7500 ⭐,
            Pro — 38 000 ⭐. Период — 30 дней, продление новой покупкой.
          </li>
          <li>
            <span className="text-[#d4ffd4] font-semibold">Возврат.</span> Команда{" "}
            <code>/refund</code> в @KitronBot — Telegram возвращает Stars на
            ваш баланс мгновенно. Тариф откатывается к free.
          </li>
        </ul>
      </section>

      {/* ─── Enterprise Section ─── */}
      <section className="mt-10 glass-card p-6 animate-fade-in-up" style={{ animationDelay: "0.2s" }}>
        <h2 className="text-[#d4ffd4] text-lg font-bold tracking-tight m-0">
          Enterprise и кастом
        </h2>
        <p className="text-[#8bb88b] text-sm mt-2.5 leading-relaxed">
          Per-engagement аудит, white-label или объёмные скидки — обсудим
          индивидуально.
        </p>
        <a
          href="https://t.me/KitronBot?start=upgrade_enterprise"
          className="inline-block mt-3.5 text-[var(--color-primary)] border border-[var(--color-primary)] px-4.5 py-2.5 rounded text-[13px] font-bold no-underline hover:bg-[var(--color-primary)] hover:text-[var(--color-bg)] hover:shadow-[0_0_20px_rgba(74,222,128,0.3)] transition-all"
        >
          Написать в Telegram
        </a>
      </section>
    </TerminalPageShell>
  );
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
      className={`
        glass-card hover-lift p-5.5 flex flex-col gap-3.5
        ${highlighted ? "glow-border animate-pulse-glow" : ""}
      `}
    >
      {/* Plan name + badge */}
      <div className="flex items-center justify-between">
        <span className="text-[#d4ffd4] font-bold text-base">{name}</span>
        {highlighted && (
          <span className="bg-[var(--color-primary)] text-[var(--color-bg)] text-[10px] px-2 py-0.5 rounded font-bold tracking-wide uppercase animate-pulse-glow">
            Рекомендуем
          </span>
        )}
      </div>

      {/* Price */}
      <div>
        <span className="text-gradient text-[30px] font-extrabold leading-none tabular-nums">
          {price}
        </span>
        <span className="text-[#8bb88b] text-xs ml-1.5">{period}</span>
      </div>

      {/* Features */}
      <ul className="list-none p-0 m-0 text-[13px] text-[#8bb88b] leading-snug">
        {features.map((f, i) => (
          <li
            key={f}
            className="py-1 flex gap-2 items-start animate-fade-in-up"
            style={{ animationDelay: `${i * 0.08}s` }}
          >
            <span className="text-[var(--color-primary)] shrink-0">+</span>
            <span>{f}</span>
          </li>
        ))}
      </ul>

      {/* CTA Button */}
      <a
        href={tgUpgradeLink(plan)}
        className={`
          mt-auto block text-center no-underline px-4 py-2.5 rounded text-[13px] font-bold transition-all
          ${
            highlighted
              ? "bg-[var(--color-primary)] text-[var(--color-bg)] hover:shadow-[0_0_24px_rgba(74,222,128,0.4)] hover:scale-105"
              : "bg-transparent text-[var(--color-primary)] border border-[var(--color-primary)] hover:bg-[var(--color-primary)] hover:text-[var(--color-bg)] hover:shadow-[0_0_20px_rgba(74,222,128,0.3)]"
          }
        `}
      >
        {ctaLabel}
      </a>
    </article>
  );
}
