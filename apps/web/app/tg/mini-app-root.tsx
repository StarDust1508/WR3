"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  type Wr3User,
  clearToken,
  fetchMe,
  fetchMyScans,
  getStoredToken,
  getWebApp,
  loginWithInitData,
  storeToken,
} from "@/lib/tg-session";
import { Logo } from "./logo";
import { MiniAppScanForm } from "./scan-form";

type ScanRow = {
  id: string;
  address: string;
  network: string;
  stage: string;
  progress: number;
  score: number | null;
  tier: string | null;
  created_at: string;
};

type Phase = "loading" | "ready" | "no-tg" | "error";

export function MiniAppRoot() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<Wr3User | null>(null);
  const [scans, setScans] = useState<ScanRow[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const tg = getWebApp();
      tg?.ready?.();
      tg?.expand?.();
      const initData = tg?.initData ?? "";
      let token = getStoredToken();
      if (!token && !initData) {
        if (!cancelled) setPhase("no-tg");
        return;
      }
      try {
        if (!token && initData) {
          const result = await loginWithInitData(initData);
          token = result.token;
          storeToken(token);
        }
        if (!token) throw new Error("no session token");
        const me = await fetchMe(token);
        if (cancelled) return;
        setUser(me);
        const myScans = await fetchMyScans(token);
        if (cancelled) return;
        setScans(myScans);
        setPhase("ready");
      } catch (e) {
        if (cancelled) return;
        clearToken();
        setError((e as Error).message);
        setPhase("error");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (phase === "loading") return <BootScreen />;
  if (phase === "no-tg") return <NotInTelegram />;
  if (phase === "error") return <AuthError message={error} />;

  return (
    <main className="mx-auto w-full max-w-xl px-4 pb-32 pt-4">
      <Header user={user} />
      <div className="tg-animate-in" style={{ animationDelay: "0.05s" }}>
        <MiniAppScanForm />
      </div>
      <div className="tg-animate-in" style={{ animationDelay: "0.15s" }}>
        <RecentScans scans={scans} />
      </div>
      <div className="tg-animate-in" style={{ animationDelay: "0.25s" }}>
        <RecentIncidents />
      </div>
      <div className="tg-animate-in" style={{ animationDelay: "0.35s" }}>
        <Footer />
      </div>
    </main>
  );
}

type IncidentRow = {
  id: string;
  title: string;
  url: string;
  source: string;
  loss_usd: number | null;
  published_at: string;
};

function RecentIncidents() {
  const [items, setItems] = useState<IncidentRow[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch("/api/v1/public/incidents?limit=3&days=60");
        if (!r.ok) return;
        const data = (await r.json()) as { incidents: IncidentRow[] };
        if (!cancelled) setItems(data.incidents);
      } catch {
        // soft-fail — widget just doesn't render
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (!items || items.length === 0) return null;

  return (
    <section className="mt-6">
      <h2 className="tg-hint mb-2 flex items-center justify-between">
        <span>Свежие эксплойты</span>
        <Link
          href="/incidents"
          className="text-[10px]"
          style={{
            color: "var(--hb-text-dim)",
            textDecoration: "none",
            transition: "color 150ms ease",
          }}
        >
          Все
        </Link>
      </h2>
      <ul className="flex flex-col gap-1.5">
        {items.map((i, idx) => (
          <li
            key={i.id}
            className="tg-animate-in"
            style={{ animationDelay: `${idx * 0.08}s` }}
          >
            <a
              href={i.url}
              target="_blank"
              rel="noopener noreferrer"
              className="tg-card-interactive flex items-start gap-3"
              style={{ padding: 10 }}
            >
              <span
                className={`source-${i.source} font-bold uppercase`}
                style={{
                  fontSize: 9,
                  marginTop: 3,
                  letterSpacing: "0.06em",
                  minWidth: 56,
                  padding: "2px 6px",
                  border: "1px solid var(--hb-border)",
                  borderRadius: 3,
                  textAlign: "center",
                }}
              >
                {sourceLabel(i.source)}
              </span>
              <div className="min-w-0 flex-1">
                <p
                  className="truncate text-xs font-medium"
                  style={{ color: "var(--hb-text-hi)" }}
                >
                  {i.title}
                </p>
                {i.loss_usd != null && (
                  <p
                    className="mt-0.5 text-[10px]"
                    style={{
                      color: "#f87171",
                      textShadow: "0 0 6px rgba(248, 113, 113, 0.3)",
                    }}
                  >
                    Убыток: ${formatIncidentLoss(i.loss_usd)}
                  </p>
                )}
              </div>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

function sourceLabel(source: string): string {
  return (
    {
      rekt: "Rekt",
      slowmist: "SlowMist",
      defillama: "DefiLlama",
    } as Record<string, string>
  )[source] ?? source;
}

function formatIncidentLoss(usd: number): string {
  if (usd >= 1_000_000_000) return `${(usd / 1_000_000_000).toFixed(1)}B`;
  if (usd >= 1_000_000) return `${(usd / 1_000_000).toFixed(1)}M`;
  if (usd >= 1_000) return `${(usd / 1_000).toFixed(0)}K`;
  return usd.toString();
}

function BootScreen() {
  return (
    <div className="flex min-h-[80vh] flex-col items-center justify-center gap-4 px-6">
      <div className="tg-logo-pulse" style={{ display: "inline-flex" }}>
        <Logo size={64} />
      </div>
      <p className="text-xs hb-dots" style={{ color: "var(--hb-text-dim)" }}>
        Загрузка
      </p>
      <div
        style={{
          width: 120,
          height: 2,
          borderRadius: 1,
          background: "var(--hb-border)",
          overflow: "hidden",
          marginTop: 4,
        }}
      >
        <div
          style={{
            width: "40%",
            height: "100%",
            background: "var(--hb-primary)",
            borderRadius: 1,
            animation: "shimmer 1.5s ease-in-out infinite",
            backgroundImage:
              "linear-gradient(90deg, var(--hb-primary) 0%, var(--hb-primary-hi) 50%, var(--hb-primary) 100%)",
            backgroundSize: "200% 100%",
          }}
        />
      </div>
    </div>
  );
}

function NotInTelegram() {
  return (
    <div className="mx-auto max-w-md px-6 pt-16 text-center">
      <div
        className="tg-glass tg-glow tg-animate-in"
        style={{ padding: "32px 24px", borderRadius: 10 }}
      >
        <div className="mb-5 inline-block tg-logo-pulse">
          <Logo size={56} />
        </div>
        <p className="text-sm font-bold" style={{ color: "var(--hb-text-hi)" }}>
          Откройте через Telegram
        </p>
        <p
          className="mt-3 text-xs"
          style={{ color: "var(--hb-text-dim)", lineHeight: 1.6 }}
        >
          wr3 — Telegram Mini App. Запустите через @KitronBot — там автоматический
          вход и доступ ко всем функциям.
        </p>
        <Link
          href="/"
          className="mt-6 inline-block text-xs"
          style={{
            color: "var(--hb-primary)",
            textDecoration: "none",
            padding: "6px 16px",
            border: "1px solid rgba(74, 222, 128, 0.25)",
            borderRadius: 4,
            transition: "all 150ms ease",
          }}
        >
          К веб-версии
        </Link>
      </div>
    </div>
  );
}

function AuthError({ message }: { message: string | null }) {
  return (
    <div className="mx-auto max-w-md px-6 pt-16 text-center">
      <div
        className="tg-animate-in"
        style={{
          background: "rgba(248, 113, 113, 0.06)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          border: "1px solid rgba(248, 113, 113, 0.20)",
          borderRadius: 10,
          padding: "32px 24px",
          boxShadow: "0 0 24px rgba(248, 113, 113, 0.08)",
        }}
      >
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: "50%",
            background: "rgba(248, 113, 113, 0.12)",
            border: "1px solid rgba(248, 113, 113, 0.25)",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: 16,
            fontSize: 18,
          }}
        >
          !
        </div>
        <p className="text-sm font-bold" style={{ color: "var(--hb-error)" }}>
          Не удалось войти
        </p>
        <p className="mt-2 text-xs" style={{ color: "var(--hb-text-dim)" }}>
          {message ?? "Неизвестная ошибка. Попробуйте ещё раз."}
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="tg-button mt-6"
          style={{
            borderColor: "var(--hb-error)",
            color: "var(--hb-error)",
          }}
        >
          Повторить
        </button>
      </div>
    </div>
  );
}

function Header({ user }: { user: Wr3User | null }) {
  const tierLabel = (user?.tier ?? "free").toLowerCase();
  const handle =
    user?.telegram_username
      ? `@${user.telegram_username}`
      : user?.display_name ?? "anon";
  return (
    <header
      className="tg-animate-in mb-5 flex items-center gap-3"
      style={{
        background: "rgba(15, 26, 15, 0.7)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        border: "1px solid rgba(74, 222, 128, 0.10)",
        borderRadius: 8,
        padding: "10px 14px",
      }}
    >
      <Logo size={36} />
      <div className="min-w-0 flex-1">
        <Link
          href="/tg/billing"
          className="inline-block text-[10px] font-bold"
          style={{
            color: "var(--hb-primary)",
            background: "rgba(74,222,128,0.10)",
            border: "1px solid rgba(74,222,128,0.35)",
            borderRadius: 3,
            padding: "1px 6px",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            textDecoration: "none",
            boxShadow: "0 0 8px rgba(74, 222, 128, 0.15)",
            transition: "box-shadow 200ms ease",
          }}
          title="Управление тарифом"
        >
          {tierLabel}
        </Link>
        <p
          className="mt-1 truncate text-sm font-bold"
          style={{ color: "var(--hb-text-hi)" }}
        >
          {handle}
        </p>
      </div>
      <Link
        href="/tg/owner"
        className="tg-button tg-button-ghost"
        style={{
          padding: "8px 12px",
          fontSize: 11,
          transition: "all 150ms ease",
          borderColor: "var(--hb-border)",
        }}
        title="Настройки пайплайна"
      >
        Настройки
      </Link>
    </header>
  );
}

function RecentScans({ scans }: { scans: ScanRow[] }) {
  if (scans.length === 0) {
    return (
      <section className="mt-5">
        <h2 className="tg-hint mb-2">Мои сканы</h2>
        <div
          className="tg-glass text-center"
          style={{ padding: "28px 16px", borderRadius: 8 }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              background: "rgba(74, 222, 128, 0.08)",
              border: "1px solid rgba(74, 222, 128, 0.15)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: 12,
              fontSize: 16,
              color: "var(--hb-primary)",
            }}
          >
            +
          </div>
          <p className="text-xs font-medium" style={{ color: "var(--hb-text-hi)" }}>
            Сканов пока нет
          </p>
          <p
            className="mt-2 text-[11px]"
            style={{ color: "var(--hb-text-dim)", lineHeight: 1.5 }}
          >
            Введите адрес контракта в форму выше — первый аудит займёт около 60 секунд.
          </p>
        </div>
      </section>
    );
  }
  return (
    <section className="mt-5">
      <h2 className="tg-hint mb-2">Мои сканы · {scans.length}</h2>
      <ul className="flex flex-col gap-2">
        {scans.map((s, idx) => (
          <li
            key={s.id}
            className="tg-animate-in"
            style={{ animationDelay: `${idx * 0.06}s` }}
          >
            <Link
              href={`/tg/scan/${s.id}`}
              className="tg-card-interactive flex items-center gap-3"
            >
              <div className="min-w-0 flex-1">
                <p
                  className="truncate text-xs font-medium"
                  style={{ color: "var(--hb-text-hi)" }}
                >
                  {shortAddr(s.address)}
                </p>
                <p
                  className="text-[10px]"
                  style={{ color: "var(--hb-text-dim)" }}
                >
                  {s.network} · {stageLabel(s.stage, s.progress)} · {relTime(s.created_at)}
                </p>
              </div>
              <ScoreBadge score={s.score} tier={s.tier} stage={s.stage} />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ScoreBadge({ score, tier, stage }: { score: number | null; tier: string | null; stage: string }) {
  if (score == null || stage !== "done") {
    return (
      <span
        className="text-[10px]"
        style={{
          color: "var(--hb-text-muted)",
          background: "rgba(84, 118, 84, 0.1)",
          padding: "4px 8px",
          borderRadius: 4,
          border: "1px solid var(--hb-border)",
        }}
      >
        ...
      </span>
    );
  }
  const tierKey = tier ?? "yellow";
  const tierClass = `tier-${tierKey}`;
  const glowClass = `tier-${tierKey}-glow`;
  return (
    <span
      className={`${tierClass} ${glowClass} text-sm font-bold`}
      style={{
        padding: "4px 10px",
        borderRadius: 4,
        background: "rgba(15, 26, 15, 0.6)",
        border: "1px solid var(--hb-border)",
      }}
    >
      {score.toFixed(0)}
    </span>
  );
}

function Footer() {
  return (
    <p
      className="mt-12 text-center text-[10px] leading-relaxed"
      style={{
        color: "var(--hb-text-muted)",
        borderTop: "1px solid var(--hb-border)",
        paddingTop: 16,
        marginLeft: "auto",
        marginRight: "auto",
        maxWidth: 280,
      }}
    >
      AI-аудит — best-effort. Для критичных контрактов рекомендуем ручное ревью.
    </p>
  );
}

function shortAddr(a: string): string {
  if (a.length <= 12) return a;
  return `${a.slice(0, 6)}…${a.slice(-4)}`;
}
function stageLabel(stage: string, progress: number): string {
  if (stage === "done") return "Готово";
  if (stage === "error") return "Ошибка";
  const ru: Record<string, string> = {
    queued: "Подготовка",
    static: "Статический анализ",
    triage: "LLM-триаж",
    poc: "PoC",
    fuzzing: "Fuzzing",
    scoring: "Оценка",
  };
  return `${ru[stage] ?? stage} · ${progress}%`;
}
function relTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (!t) return "";
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60_000);
  if (min < 1) return "сейчас";
  if (min < 60) return `${min}мин`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}ч`;
  return `${Math.floor(hr / 24)}д`;
}
