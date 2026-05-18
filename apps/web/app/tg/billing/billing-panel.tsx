"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getStoredToken } from "@/lib/tg-session";

type Subscription = {
  active: boolean;
  plan: string;
  tier: string;
  provider?: string;
  period_start?: string;
  period_end?: string | null;
  amount?: number;
  currency?: string;
};

type Plan = { plan: string; stars: number };

const PLAN_BLURB: Record<string, string> = {
  hobby: "10 контрактов / мес · multi-agent триаж · PoC retry-loop",
  team:  "Безлимит · AI-fuzzing · мониторинг каждые 6 ч",
  pro:   "Всё из Team + расширенный LLM-триаж и кастомные инварианты",
};

/**
 * Billing panel. Read-only — writes happen via Stars payment in the bot,
 * not via this UI. We just show what's active and link out for upgrade.
 *
 * Why no in-Mini-App invoice button: telegram-web-app SDK has
 * `openInvoice(url)` but it requires a slug from `createInvoiceLink` (Bot
 * API method), which would need a server round-trip per click. Deep-linking
 * `t.me/KitronBot?start=upgrade_<plan>` is one-tap, has zero infra, and
 * leaves the source-of-truth in the bot conversation — easier for support.
 */
export function BillingPanel() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = getStoredToken();
        if (!token) throw new Error("не авторизован");
        const headers = { Authorization: `Bearer ${token}` };
        const [meRes, plansRes] = await Promise.all([
          fetch("/api/v1/subscription/me", { headers }),
          fetch("/api/v1/subscription/plans"),
        ]);
        if (!meRes.ok) throw new Error(`subscription failed (${meRes.status})`);
        const me = (await meRes.json()) as Subscription;
        const plansData = plansRes.ok
          ? ((await plansRes.json()) as { plans: Plan[] })
          : { plans: [] };
        if (cancelled) return;
        setSub(me);
        setPlans(plansData.plans);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <main className="mx-auto max-w-xl px-4 pb-32 pt-4">
      <BackLink />

      <h1
        className="tg-animate-in tg-delay-1 mt-4 text-lg font-bold"
        style={{ color: "var(--hb-text-hi)" }}
      >
        Тариф
      </h1>
      <p
        className="tg-animate-in tg-delay-2 mt-1 text-[12px] leading-relaxed"
        style={{ color: "var(--hb-text-dim)" }}
      >
        Оплата через Telegram Stars прямо в боте. Без карт, без KYC.
      </p>

      {error && (
        <p
          className="tg-glass tg-animate-in mt-3 text-xs leading-relaxed"
          style={{
            color: "var(--hb-error)",
            borderColor: "rgba(248,113,113,0.30)",
          }}
        >
          {error}
        </p>
      )}

      {sub === null && !error ? (
        <p
          className="mt-8 text-center text-xs hb-dots"
          style={{ color: "var(--hb-text-dim)" }}
        >
          Загрузка
        </p>
      ) : sub ? (
        <div className="tg-animate-in tg-delay-3">
          <CurrentPlan sub={sub} />
        </div>
      ) : null}

      <section className="tg-animate-in tg-delay-4 mt-6">
        <h2 className="tg-hint mb-2">Купить или продлить</h2>
        <div className="flex flex-col gap-2">
          {plans.length === 0 ? (
            <p className="text-[11px]" style={{ color: "var(--hb-text-dim)" }}>
              Каталог временно недоступен.
            </p>
          ) : (
            plans.map((p, i) => (
              <div
                key={p.plan}
                className="tg-animate-in"
                style={{ animationDelay: `${0.24 + i * 0.08}s` }}
              >
                <PlanRow
                  plan={p.plan}
                  stars={p.stars}
                  isCurrent={sub?.active && sub.plan === p.plan}
                />
              </div>
            ))
          )}
        </div>
      </section>

      <p
        className="tg-animate-in tg-delay-7 mt-8 text-center text-[10px] leading-relaxed"
        style={{ color: "var(--hb-text-dim)" }}
      >
        Возврат Stars — командой <code>/refund</code> в боте, в течение 14 дней.
      </p>
    </main>
  );
}

function BackLink() {
  return (
    <Link
      href="/tg"
      className="inline-flex items-center gap-1 text-xs"
      style={{
        color: "var(--hb-text-dim)",
        textDecoration: "none",
        transition: "color 0.2s ease",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.color = "var(--hb-primary)")}
      onMouseLeave={(e) => (e.currentTarget.style.color = "var(--hb-text-dim)")}
    >
      <span style={{ fontSize: 16, lineHeight: 1 }}>‹</span>
      {" "}Назад
    </Link>
  );
}

function CurrentPlan({ sub }: { sub: Subscription }) {
  if (!sub.active) {
    return (
      <div className="tg-glass tg-glow mt-4">
        <p className="tg-hint mb-1">Текущий тариф</p>
        <p
          className="text-base font-bold"
          style={{ color: "var(--hb-text-hi)" }}
        >
          Free
        </p>
        <p
          className="mt-2 text-[11px] leading-relaxed"
          style={{ color: "var(--hb-text-dim)" }}
        >
          1 контракт в сутки. Baseline-статика + single-call триаж.
        </p>
      </div>
    );
  }
  const endStr = sub.period_end
    ? new Date(sub.period_end).toLocaleDateString("ru-RU", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : "—";
  return (
    <div className="tg-glass tg-glow mt-4">
      <p className="tg-hint mb-1">Текущий тариф</p>
      <p
        className="text-base font-bold capitalize"
        style={{ color: "var(--hb-text-hi)" }}
      >
        {sub.plan}
        <span
          className="ml-2 text-xs font-normal"
          style={{ color: "var(--hb-text-dim)" }}
        >
          до {endStr}
        </span>
      </p>
      <p
        className="mt-2 text-[11px] leading-relaxed"
        style={{ color: "var(--hb-text-dim)" }}
      >
        {PLAN_BLURB[sub.plan] ?? ""}
      </p>
      {sub.amount && sub.currency === "XTR" && (
        <p className="mt-2 text-[10px]" style={{ color: "var(--hb-text-dim)" }}>
          Оплачено:{" "}
          <span style={{ color: "#fbbf24", fontWeight: 700 }}>{sub.amount}</span>
          {" "}
          <span style={{ color: "#fbbf24" }}>&#11088;</span>
        </p>
      )}
      {sub.provider === "telegram_stars" && (
        <a
          href="https://t.me/KitronBot?start=refund"
          className="tg-underline-anim mt-3 inline-block text-[11px]"
          style={{
            color: "var(--hb-text-dim)",
          }}
        >
          Вернуть Stars (открыть бота)
        </a>
      )}
    </div>
  );
}

function PlanRow({ plan, stars, isCurrent }: { plan: string; stars: number; isCurrent?: boolean }) {
  const href = `https://t.me/KitronBot?start=upgrade_${plan}`;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="tg-glass flex items-center gap-3"
      style={{
        textDecoration: "none",
        transition: "border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease",
        cursor: "pointer",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "rgba(74, 222, 128, 0.3)";
        e.currentTarget.style.boxShadow = "0 0 20px rgba(74, 222, 128, 0.08)";
        e.currentTarget.style.background = "rgba(15, 26, 15, 0.8)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "rgba(74, 222, 128, 0.12)";
        e.currentTarget.style.boxShadow = "none";
        e.currentTarget.style.background = "rgba(15, 26, 15, 0.6)";
      }}
    >
      <div className="min-w-0 flex-1">
        <p
          className="text-sm font-bold capitalize"
          style={{ color: "var(--hb-text-hi)" }}
        >
          {plan}
          {isCurrent && (
            <span
              className="ml-2 tg-chip sev-chip-good"
              style={{ animation: "green-pulse 2s ease-in-out infinite" }}
            >
              Активен
            </span>
          )}
        </p>
        <p
          className="mt-0.5 text-[11px] leading-relaxed"
          style={{ color: "var(--hb-text-dim)" }}
        >
          {PLAN_BLURB[plan] ?? ""}
        </p>
      </div>
      <span
        className="text-xs font-bold"
        style={{ color: "#fbbf24", whiteSpace: "nowrap" }}
      >
        {stars} &#11088;
      </span>
    </a>
  );
}
