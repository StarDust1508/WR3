"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Loader2,
  ShieldCheck,
  ShieldOff,
} from "lucide-react";
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

    async function boot() {
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
        // Token may be stale (server restarted with a new JWT secret).
        // Drop it and let the user re-open the Mini App to retrigger initData.
        clearToken();
        setError((e as Error).message);
        setPhase("error");
      }
    }

    boot();
    return () => {
      cancelled = true;
    };
  }, []);

  if (phase === "loading") return <CenteredLoading />;
  if (phase === "no-tg") return <NotInTelegram />;
  if (phase === "error") return <AuthError message={error} />;

  return (
    <main className="mx-auto w-full max-w-xl px-4 pb-32 pt-4">
      <Header user={user} />
      <MiniAppScanForm />
      <RecentScans scans={scans} />
      <Disclaimer />
    </main>
  );
}

function CenteredLoading() {
  return (
    <div className="flex min-h-[80vh] flex-col items-center justify-center gap-3">
      <Logo size={56} />
      <Loader2 className="animate-spin" size={20} color="var(--tg-hint)" aria-hidden />
    </div>
  );
}

function NotInTelegram() {
  return (
    <div className="mx-auto max-w-md px-6 pt-16 text-center">
      <div className="mx-auto mb-4 w-fit"><Logo size={56} /></div>
      <h1 className="mb-2 text-lg font-semibold" style={{ color: "var(--tg-text)" }}>
        Open this from Telegram
      </h1>
      <p className="text-sm" style={{ color: "var(--tg-hint)" }}>
        wr3 is a Telegram Mini App. Open it via the wr3 bot to sign in.
      </p>
      <Link
        href="/"
        className="mt-6 inline-flex items-center gap-1 text-sm"
        style={{ color: "var(--tg-link)" }}
      >
        Use the web version <ArrowRight size={14} />
      </Link>
    </div>
  );
}

function AuthError({ message }: { message: string | null }) {
  return (
    <div className="mx-auto max-w-md px-6 pt-16 text-center">
      <div
        className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full"
        style={{ background: "color-mix(in srgb, var(--tg-destructive) 18%, transparent)" }}
      >
        <ShieldOff size={22} color="var(--tg-destructive)" />
      </div>
      <h1 className="mb-2 text-lg font-semibold" style={{ color: "var(--tg-text)" }}>
        Sign-in failed
      </h1>
      <p className="text-sm" style={{ color: "var(--tg-hint)" }}>
        {message ?? "Unknown error"}
      </p>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="tg-button mt-6"
        style={{ minWidth: 160 }}
      >
        Try again
      </button>
    </div>
  );
}

function Header({ user }: { user: Wr3User | null }) {
  const tierLabel = (user?.tier ?? "free").toUpperCase();
  return (
    <header className="mb-6 flex items-center gap-3">
      <Logo size={40} />
      <div className="min-w-0">
        <p className="tg-hint" style={{ fontSize: 10 }}>{tierLabel} TIER</p>
        <h1 className="truncate text-xl font-semibold" style={{ color: "var(--tg-text)" }}>
          {user?.display_name ??
            (user?.telegram_username ? `@${user.telegram_username}` : "wr3")}
        </h1>
      </div>
    </header>
  );
}

function RecentScans({ scans }: { scans: ScanRow[] }) {
  if (scans.length === 0) {
    return (
      <section className="mt-6">
        <h2 className="tg-hint mb-2">Your recent scans</h2>
        <div className="tg-card flex flex-col items-center gap-2 py-8 text-center">
          <ShieldCheck size={32} color="var(--tg-hint)" aria-hidden />
          <p className="text-sm" style={{ color: "var(--tg-hint)" }}>
            No scans yet. Paste a contract above to start your first audit.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="mt-6">
      <h2 className="tg-hint mb-2">Your recent scans</h2>
      <ul className="flex flex-col gap-2">
        {scans.map((s) => (
          <li key={s.id}>
            <Link
              href={`/tg/scan/${s.id}`}
              className="tg-card flex items-center gap-3 active:scale-[0.99]"
              style={{ transition: "transform 80ms" }}
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-mono text-sm" style={{ color: "var(--tg-text)" }}>
                  {shortenAddress(s.address)}
                </p>
                <p className="text-xs" style={{ color: "var(--tg-hint)" }}>
                  {s.network} · {scanStageLabel(s.stage, s.progress)} ·{" "}
                  {relativeTime(s.created_at)}
                </p>
              </div>
              <ScoreBadge score={s.score} tier={s.tier} stage={s.stage} />
              <ArrowRight size={16} color="var(--tg-hint)" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ScoreBadge({
  score,
  tier,
  stage,
}: {
  score: number | null;
  tier: string | null;
  stage: string;
}) {
  if (score == null || stage !== "done") {
    return (
      <span className="flex items-center gap-1 text-xs" style={{ color: "var(--tg-hint)" }}>
        <Loader2 size={12} className="animate-spin" />
        running
      </span>
    );
  }
  const tierClass = `tier-${tier ?? "yellow"}`;
  const Icon = tier === "red" ? AlertTriangle : ShieldCheck;
  return (
    <span className={`flex shrink-0 items-center gap-1 ${tierClass}`}>
      <Icon size={14} />
      <span className="text-base font-bold">{score.toFixed(0)}</span>
    </span>
  );
}

function Disclaimer() {
  return (
    <p
      className="mt-10 text-center text-[11px] leading-relaxed"
      style={{ color: "var(--tg-hint)" }}
    >
      AI-assisted audit. Best-effort, no warranty. Not a replacement for human review.
    </p>
  );
}

function shortenAddress(addr: string): string {
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

function scanStageLabel(stage: string, progress: number): string {
  if (stage === "done") return "done";
  if (stage === "error") return "failed";
  return `${stage} ${progress}%`;
}

function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (!t) return "";
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const d = Math.floor(hr / 24);
  return `${d}d ago`;
}
