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
      <Link href="/tg" className="text-xs" style={{ color: "var(--hb-text-dim)" }}>
        ← назад
      </Link>

      <h1 className="mt-4 text-sm hb-prompt" style={{ color: "var(--hb-text-hi)" }}>
        тариф<span className="hb-cursor" />
      </h1>
      <p className="mt-1 text-[11px]" style={{ color: "var(--hb-text-muted)" }}>
        // оплата через telegram stars — в один тап, без карт
      </p>

      {error && (
        <p className="mt-3 text-xs" style={{ color: "var(--hb-error)" }}>
          <span>ERR </span>{error}
        </p>
      )}

      {sub === null && !error ? (
        <p className="mt-8 text-center text-xs hb-prompt">
          загрузка<span className="hb-cursor" />
        </p>
      ) : sub ? (
        <CurrentPlan sub={sub} />
      ) : null}

      <section className="mt-6">
        <h2 className="tg-hint mb-2">купить / продлить</h2>
        <div className="flex flex-col gap-2">
          {plans.length === 0 ? (
            <p className="text-[11px]" style={{ color: "var(--hb-text-muted)" }}>
              каталог недоступен
            </p>
          ) : (
            plans.map((p) => (
              <PlanRow
                key={p.plan}
                plan={p.plan}
                stars={p.stars}
                isCurrent={sub?.active && sub.plan === p.plan}
              />
            ))
          )}
        </div>
      </section>

      <p className="mt-8 text-center text-[10px]" style={{ color: "var(--hb-text-muted)" }}>
        возврат stars — через `/refund` в боте в течение 14 дней
      </p>
    </main>
  );
}

function CurrentPlan({ sub }: { sub: Subscription }) {
  if (!sub.active) {
    return (
      <div className="tg-card mt-4">
        <p className="tg-hint mb-1">сейчас</p>
        <p className="text-sm font-bold" style={{ color: "var(--hb-text-hi)" }}>
          free <span style={{ color: "var(--hb-text-muted)", fontWeight: 400 }}>· без оплаты</span>
        </p>
        <p className="mt-2 text-[11px]" style={{ color: "var(--hb-text-muted)" }}>
          1 контракт / 24 ч. Baseline-статика + single-call триаж.
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
    <div className="tg-card mt-4">
      <p className="tg-hint mb-1">сейчас</p>
      <p className="text-sm font-bold" style={{ color: "var(--hb-text-hi)" }}>
        {sub.plan}{" "}
        <span style={{ color: "var(--hb-text-muted)", fontWeight: 400 }}>
          · до {endStr}
        </span>
      </p>
      <p className="mt-2 text-[11px]" style={{ color: "var(--hb-text-muted)" }}>
        {PLAN_BLURB[sub.plan] ?? ""}
      </p>
      {sub.amount && sub.currency === "XTR" && (
        <p className="mt-1 text-[10px]" style={{ color: "var(--hb-text-dim)" }}>
          оплачено {sub.amount} ⭐
        </p>
      )}
      {sub.provider === "telegram_stars" && (
        <a
          href="https://t.me/KitronBot?start=refund"
          className="mt-3 inline-block text-[11px]"
          style={{
            color: "var(--hb-text-muted)",
            textDecoration: "underline",
          }}
        >
          вернуть Stars (откроет бота)
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
      className="tg-card-interactive flex items-center gap-3"
    >
      <span style={{ color: "var(--hb-text-muted)", fontSize: 11 }}>$</span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-bold" style={{ color: "var(--hb-text-hi)" }}>
          {plan}
          {isCurrent && (
            <span className="ml-2 tg-chip sev-chip-good" style={{ textTransform: "lowercase" }}>
              активен
            </span>
          )}
        </p>
        <p className="text-[11px]" style={{ color: "var(--hb-text-muted)" }}>
          {PLAN_BLURB[plan] ?? ""}
        </p>
      </div>
      <span className="text-xs font-bold" style={{ color: "var(--hb-primary)" }}>
        {stars} ⭐
      </span>
    </a>
  );
}
