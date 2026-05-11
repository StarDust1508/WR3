"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Stage = "queued" | "static" | "triage" | "poc" | "fuzzing" | "scoring" | "done" | "error";

interface ScanState {
  stage: Stage;
  progress: number;
  score?: number;
  message?: string;
  scan_id?: string;
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
          setState((s) => ({ ...s, stage: "error", message: "Stream closed" }));
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
    <div className="space-y-6">
      <ProgressBar progress={state.progress} stage={state.stage} />
      <StageLabel stage={state.stage} />
      {state.message && <p className="text-sm text-red-600">{state.message}</p>}
      {state.stage === "done" && state.score !== undefined && <ScoreCard score={state.score} />}
    </div>
  );
}

function ProgressBar({ progress, stage }: { progress: number; stage: Stage }) {
  const color = stage === "error" ? "bg-red-500" : "bg-zinc-900 dark:bg-zinc-50";
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
      <div
        className={`h-full transition-all duration-300 ${color}`}
        style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
      />
    </div>
  );
}

function StageLabel({ stage }: { stage: Stage }) {
  const labels: Record<Stage, string> = {
    queued: "Queued — preparing pipeline",
    static: "Running Aderyn + Wake + Slither (static analysis)",
    triage: "LLM triage — filtering false positives",
    poc: "Generating Foundry PoC for high-severity findings",
    fuzzing: "AI-fuzzing with generated invariants",
    scoring: "Computing 0–100 score across 5 axes",
    done: "Done",
    error: "Error",
  };
  return <p className="text-sm text-zinc-600 dark:text-zinc-400">{labels[stage]}</p>;
}

function ScoreCard({ score }: { score: number }) {
  const tier =
    score >= 90 ? "blue" : score >= 70 ? "green" : score >= 40 ? "yellow" : "red";
  const colorMap = {
    red: "text-red-600 border-red-200 dark:border-red-900",
    yellow: "text-yellow-600 border-yellow-200 dark:border-yellow-900",
    green: "text-green-600 border-green-200 dark:border-green-900",
    blue: "text-blue-600 border-blue-200 dark:border-blue-900",
  };
  return (
    <div className={`rounded-lg border p-6 ${colorMap[tier]}`}>
      <p className="text-sm uppercase tracking-wide text-zinc-500">Security score</p>
      <p className="mt-2 text-6xl font-bold">{score}</p>
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
        Detailed findings, Foundry PoCs, and per-axis breakdown require a paid plan.
      </p>
    </div>
  );
}
