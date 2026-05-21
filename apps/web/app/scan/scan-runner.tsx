"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";

type Stage = "queued" | "static" | "triage" | "poc" | "fuzzing" | "scoring" | "done" | "error";

interface ScanState {
  stage: Stage;
  progress: number;
  score?: number;
  message?: string;
  scan_id?: string;
}

const STAGES: { id: Stage; label: string; icon: string }[] = [
  { id: "queued", label: "Queue", icon: "⏳" },
  { id: "static", label: "Static", icon: "🔍" },
  { id: "triage", label: "Triage", icon: "🧠" },
  { id: "poc", label: "PoC", icon: "⚡" },
  { id: "fuzzing", label: "Fuzz", icon: "🎯" },
  { id: "scoring", label: "Score", icon: "📊" },
  { id: "done", label: "Done", icon: "✓" },
];

function getStageIndex(stage: Stage): number {
  if (stage === "error") return -1;
  return STAGES.findIndex((s) => s.id === stage);
}

export function ScanRunner({ address, network }: { address: string; network: string }) {
  const [state, setState] = useState<ScanState>({ stage: "queued", progress: 0 });
  const router = useRouter();

  useEffect(() => {
    const controller = new AbortController();

    async function run() {
      try {
        const res = await fetch(`/api/v1/scan`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ address, network }),
          signal: controller.signal,
        });

        if (!res.ok) {
          throw new Error(`API returned ${res.status}`);
        }

        const { job_id: jobId } = (await res.json()) as { job_id: string };

        const es = new EventSource(`/api/v1/scan/${jobId}/events`);
        es.onmessage = (e) => {
          const update = JSON.parse(e.data) as ScanState;
          setState(update);
          if (update.stage === "done") {
            es.close();
            if (update.scan_id) {
              router.push(`/scan/${update.scan_id}`);
            }
          } else if (update.stage === "error") {
            es.close();
          }
        };
        es.onerror = () => {
          es.close();
          setState((s) => ({ ...s, stage: "error", message: "Соединение закрыто" }));
        };
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setState({ stage: "error", progress: 0, message: (err as Error).message });
        }
      }
    }

    run();
    return () => controller.abort();
  }, [address, network, router]);

  return (
    <div className="rounded-2xl border border-[#1a2e1a]/60 bg-[#0c120c] space-y-10 p-8 md:p-10">
      <ProgressBar progress={state.progress} stage={state.stage} />
      <Stepper stage={state.stage} />
      {state.message && (
        <p className="animate-[shake_0.5s_ease-in-out] rounded-xl border border-red-500/30 bg-red-500/8 px-5 py-4 text-base text-red-400">
          {state.message}
        </p>
      )}
      {state.stage === "done" && state.score !== undefined && <ScoreCard score={state.score} />}
    </div>
  );
}

function ProgressBar({ progress, stage }: { progress: number; stage: Stage }) {
  const isError = stage === "error";
  const pct = Math.min(100, Math.max(0, progress));

  return (
    <div className="relative h-5 w-full overflow-hidden rounded-full bg-[#0a0e0a] border border-[#1a2e1a]/60">
      {/* Glow trail background */}
      <div
        className={[
          "absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out",
          isError
            ? "bg-gradient-to-r from-red-600 to-red-400 shadow-[0_0_16px_rgba(248,113,113,0.5)]"
            : "bg-gradient-to-r from-emerald-600 via-[#4ade80] to-[#d4ffd4] shadow-[0_0_20px_rgba(74,222,128,0.4)]",
        ].join(" ")}
        style={{ width: `${pct}%` }}
      />
      {/* Shimmer overlay on the progress fill */}
      {!isError && pct > 0 && (
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer"
          style={{ width: `${pct}%` }}
        />
      )}
      {/* Pulse on error */}
      {isError && (
        <div className="absolute inset-0 rounded-full bg-red-500/20 animate-pulse" />
      )}
    </div>
  );
}

function Stepper({ stage }: { stage: Stage }) {
  const currentIdx = getStageIndex(stage);
  const isError = stage === "error";

  return (
    <div className="flex items-center justify-between">
      {STAGES.map((s, i) => {
        const isDone = currentIdx > i;
        const isCurrent = currentIdx === i;
        const isFuture = currentIdx < i;

        return (
          <div key={s.id} className="flex flex-1 items-center">
            {/* Node */}
            <div className="flex flex-col items-center gap-2">
              <div
                className={[
                  "relative flex h-11 w-11 items-center justify-center rounded-full border-2 text-base transition-all duration-300",
                  isDone
                    ? "border-[#4ade80] bg-[#4ade80]/20 text-[#4ade80]"
                    : isCurrent
                      ? isError
                        ? "border-red-500 bg-red-500/20 text-red-400"
                        : "border-[#4ade80] bg-[#4ade80]/10 text-[#4ade80]"
                      : "border-[#547654]/50 bg-transparent text-[#547654]",
                ].join(" ")}
              >
                {/* Pulsing ring on current */}
                {isCurrent && !isError && (
                  <span className="absolute inset-0 rounded-full border-2 border-[#4ade80] animate-ping opacity-30" />
                )}
                {isCurrent && isError && (
                  <span className="absolute inset-0 rounded-full border-2 border-red-500 animate-ping opacity-30" />
                )}
                <span className="relative text-sm">{isDone ? "✓" : s.icon}</span>
              </div>
              <span
                className={[
                  "text-xs font-semibold tracking-wide transition-colors duration-300",
                  isDone
                    ? "text-[#4ade80]"
                    : isCurrent
                      ? isError
                        ? "text-red-400"
                        : "text-[#d4ffd4]"
                      : "text-[#547654]",
                ].join(" ")}
              >
                {s.label}
              </span>
            </div>

            {/* Connector line */}
            {i < STAGES.length - 1 && (
              <div className="mx-1 h-0.5 flex-1 rounded-full bg-[#547654]/30 overflow-hidden">
                <div
                  className={[
                    "h-full rounded-full transition-all duration-500",
                    isDone
                      ? "w-full bg-[var(--color-primary)]/60"
                      : isCurrent
                        ? "w-1/2 bg-[var(--color-primary)]/30"
                        : "w-0",
                  ].join(" ")}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ScoreCard({ score }: { score: number }) {
  const [displayed, setDisplayed] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    let frame: number;
    const duration = 1500;
    const start = performance.now();

    function animate(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayed(Math.round(eased * score));
      if (progress < 1) {
        frame = requestAnimationFrame(animate);
      }
    }

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [score]);

  const tier =
    score >= 90 ? "blue" : score >= 70 ? "green" : score >= 40 ? "yellow" : "red";

  const colorMap = {
    red: {
      text: "text-red-400",
      border: "border-red-500/40",
      glow: "shadow-[0_0_30px_rgba(248,113,113,0.2)]",
      bg: "bg-red-500/5",
    },
    yellow: {
      text: "text-yellow-400",
      border: "border-yellow-500/40",
      glow: "shadow-[0_0_30px_rgba(250,204,21,0.2)]",
      bg: "bg-yellow-500/5",
    },
    green: {
      text: "text-[var(--color-primary)]",
      border: "border-[var(--color-primary)]/40",
      glow: "shadow-[0_0_30px_rgba(74,222,128,0.2)]",
      bg: "bg-[var(--color-primary)]/5",
    },
    blue: {
      text: "text-blue-400",
      border: "border-blue-500/40",
      glow: "shadow-[0_0_30px_rgba(96,165,250,0.2)]",
      bg: "bg-blue-500/5",
    },
  };

  const c = colorMap[tier];

  return (
    <div
      className={[
        "relative overflow-hidden rounded-2xl border p-8 text-center",
        "animate-fade-in-up",
        c.border,
        c.glow,
        c.bg,
      ].join(" ")}
    >
      {/* Background shimmer */}
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.02] to-transparent animate-shimmer" />

      <p className="text-sm font-semibold uppercase tracking-[0.15em] text-[#8bb88b]">
        Security Score
      </p>
      <p className={`relative mt-4 text-[80px] leading-none font-black tabular-nums ${c.text}`}>
        <span ref={ref}>{displayed}</span>
      </p>
      <p className="mt-4 text-base text-[#8bb88b]/80">
        Детальные находки, Foundry PoC и разбивка по осям — на платных тарифах.
      </p>
    </div>
  );
}
