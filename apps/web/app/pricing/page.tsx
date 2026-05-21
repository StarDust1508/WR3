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
      <p className="text-[#8bb88b] text-base leading-relaxed">
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
      <section className="mt-12 rounded-2xl border border-[#1a2e1a]/60 bg-[#0c120c] p-8 animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
        <h2 className="text-[#e2ffe2] text-xl font-bold tracking-tight m-0">
          Оплата
        </h2>
        <ul className="text-[#8bb88b] text-base leading-relaxed mt-4 pl-5 list-disc">
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
      <section className="mt-10 rounded-2xl border border-[#1a2e1a]/60 bg-[#0c120c] p-8 animate-fade-in-up" style={{ animationDelay: "0.2s" }}>
        <h2 className="text-[#e2ffe2] text-xl font-bold tracking-tight m-0">
          Enterprise и кастом
        </h2>
        <p className="text-[#8bb88b] text-base mt-3 leading-relaxed">
          Per-engagement аудит, white-label или объёмные скидки — обсудим
          индивидуально.
        </p>
        <a
          href="https://t.me/KitronBot?start=upgrade_enterprise"
          className="inline-block mt-4 text-[#4ade80] border border-[#4ade80] px-5 py-3 rounded-lg text-sm font-bold no-underline hover:bg-[#4ade80] hover:text-[#060a06] hover:shadow-[0_0_20px_rgba(74,222,128,0.3)] transition-all"
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
        rounded-2xl border border-[#1a2e1a]/60 bg-[#0c120c] p-6 flex flex-col gap-4 transition-all hover:border-[#1a2e1a]
        ${highlighted ? "border-[#4ade80]/40 shadow-[0_0_24px_rgba(74,222,128,0.1)]" : ""}
      `}
    >
      {/* Plan name + badge */}
      <div className="flex items-center justify-between">
        <span className="text-[#e2ffe2] font-bold text-lg">{name}</span>
        {highlighted && (
          <span className="bg-[#4ade80] text-[#060a06] text-xs px-2.5 py-1 rounded-lg font-bold tracking-wide uppercase">
            Рекомендуем
          </span>
        )}
      </div>

      {/* Price */}
      <div>
        <span className="text-[#4ade80] text-4xl font-extrabold leading-none tabular-nums">
          {price}
        </span>
        <span className="text-[#8bb88b] text-sm ml-2">{period}</span>
      </div>

      {/* Features */}
      <ul className="list-none p-0 m-0 text-sm text-[#8bb88b] leading-relaxed">
        {features.map((f, i) => (
          <li
            key={f}
            className="py-1.5 flex gap-2.5 items-start animate-fade-in-up"
            style={{ animationDelay: `${i * 0.08}s` }}
          >
            <span className="text-[#4ade80] shrink-0 font-bold">+</span>
            <span>{f}</span>
          </li>
        ))}
      </ul>

      {/* CTA Button */}
      <a
        href={tgUpgradeLink(plan)}
        className={`
          mt-auto block text-center no-underline px-5 py-3 rounded-lg text-sm font-bold transition-all
          ${
            highlighted
              ? "bg-[#4ade80] text-[#060a06] hover:shadow-[0_0_24px_rgba(74,222,128,0.4)] hover:scale-105"
              : "bg-transparent text-[#4ade80] border border-[#4ade80] hover:bg-[#4ade80] hover:text-[#060a06] hover:shadow-[0_0_20px_rgba(74,222,128,0.3)]"
          }
        `}
      >
        {ctaLabel}
      </a>
    </article>
  );
}
