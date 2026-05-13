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
      <MiniAppScanForm />
      <RecentScans scans={scans} />
      <RecentIncidents />
      <Footer />
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
          style={{ color: "var(--hb-text-dim)", textDecoration: "none" }}
        >
          Все
        </Link>
      </h2>
      <ul className="flex flex-col gap-1.5">
        {items.map((i) => (
          <li key={i.id}>
            <a
              href={i.url}
              target="_blank"
              rel="noopener noreferrer"
              className="tg-card-interactive flex items-start gap-2"
              style={{ padding: 10 }}
            >
              <span
                className="font-bold uppercase"
                style={{
                  color: "var(--hb-text-dim)",
                  fontSize: 9,
                  marginTop: 3,
                  letterSpacing: "0.06em",
                  minWidth: 56,
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
                  <p className="mt-0.5 text-[10px]" style={{ color: "#f87171" }}>
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
    <div className="flex min-h-[80vh] flex-col items-center justify-center gap-3 px-6">
      <Logo size={56} />
      <p className="text-xs hb-dots" style={{ color: "var(--hb-text-dim)" }}>
        Загрузка
      </p>
    </div>
  );
}

function NotInTelegram() {
  return (
    <div className="mx-auto max-w-md px-6 pt-16 text-center">
      <div className="mb-4 inline-block"><Logo size={56} /></div>
      <p className="text-sm font-bold" style={{ color: "var(--hb-text-hi)" }}>
        Откройте через Telegram
      </p>
      <p className="mt-3 text-xs" style={{ color: "var(--hb-text-dim)" }}>
        wr3 — Telegram Mini App. Запустите через @KitronBot — там автоматический
        вход и доступ ко всем функциям.
      </p>
      <Link
        href="/"
        className="mt-6 inline-block text-xs underline"
        style={{ color: "var(--hb-text-dim)" }}
      >
        К веб-версии
      </Link>
    </div>
  );
}

function AuthError({ message }: { message: string | null }) {
  return (
    <div className="mx-auto max-w-md px-6 pt-16 text-center">
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
      >
        Повторить
      </button>
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
    <header className="mb-5 flex items-center gap-3">
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
        style={{ padding: "8px 12px", fontSize: 11 }}
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
        <div className="tg-card text-center" style={{ padding: "24px 12px" }}>
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
        {scans.map((s) => (
          <li key={s.id}>
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
      <span className="text-[10px]" style={{ color: "var(--hb-text-muted)" }}>
        ...
      </span>
    );
  }
  const tierClass = `tier-${tier ?? "yellow"}`;
  return (
    <span className={`${tierClass} text-sm font-bold`}>{score.toFixed(0)}</span>
  );
}

function Footer() {
  return (
    <p
      className="mt-12 text-center text-[10px] leading-relaxed"
      style={{ color: "var(--hb-text-dim)" }}
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
