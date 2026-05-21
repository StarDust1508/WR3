"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { LiveFeed } from "@/components/live-feed";
import { ScanInput } from "@/components/scan-input";

type Stage = "queued" | "static" | "triage" | "poc" | "fuzzing" | "scoring" | "done" | "error";

interface ScanState {
  stage: Stage;
  progress: number;
  score?: number;
  message?: string;
  scan_id?: string;
}

interface ScanSummary {
  id: string;
  score: number | null;
  tier: string | null;
  findingsCount: number;
  criticalCount: number;
  highCount: number;
}

const STAGES: { id: Stage; label: string; desc: string; estimate: string }[] = [
  { id: "queued", label: "Queue", desc: "Подготовка и загрузка исходного кода", estimate: "~5с" },
  { id: "static", label: "Static", desc: "4 анализатора сканируют код параллельно", estimate: "~15с" },
  { id: "triage", label: "Triage", desc: "4 AI-агента фильтруют false positive", estimate: "~30с" },
  { id: "poc", label: "PoC", desc: "Генерация Foundry-тестов для уязвимостей", estimate: "~60с" },
  { id: "fuzzing", label: "Fuzz", desc: "Invariant-тестирование через Medusa", estimate: "~30с" },
  { id: "scoring", label: "Score", desc: "Расчёт score + on-chain enrichment", estimate: "~10с" },
  { id: "done", label: "Done", desc: "Аудит завершён", estimate: "" },
];

function shortAddr(a: string): string {
  if (a.length <= 14) return a;
  return `${a.slice(0, 6)}…${a.slice(-4)}`;
}

export function HeroWithFeed() {
  const [selectedAddress, setSelectedAddress] = useState("");
  const [selectedNetwork, setSelectedNetwork] = useState("ethereum");
  const [scanning, setScanning] = useState<{ address: string; network: string } | null>(null);
  const [scanState, setScanState] = useState<ScanState>({ stage: "queued", progress: 0 });
  const [scanSummary, setScanSummary] = useState<ScanSummary | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  function handleSelectToken(address: string, network: string) {
    setSelectedAddress(address);
    setSelectedNetwork(network);
  }

  function handleScan(address: string, network: string) {
    setScanning({ address, network });
    setScanState({ stage: "queued", progress: 0 });
  }

  function handleBack() {
    if (abortRef.current) abortRef.current.abort();
    setScanning(null);
    setScanState({ stage: "queued", progress: 0 });
    setScanSummary(null);
  }

  const runScan = useCallback(async (address: string, network: string, signal: AbortSignal) => {
    try {
      const res = await fetch(`/api/v1/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address, network }),
        signal,
      });

      if (!res.ok) {
        throw new Error(`API ${res.status}`);
      }

      const { job_id: jobId } = (await res.json()) as { job_id: string };

      const es = new EventSource(`/api/v1/scan/${jobId}/events`);
      signal.addEventListener("abort", () => es.close());

      es.onmessage = (e) => {
        const update = JSON.parse(e.data) as ScanState;
        setScanState(update);
        if (update.stage === "done") {
          es.close();
          if (update.scan_id) {
            fetch(`/api/v1/scan/${update.scan_id}`)
              .then((r) => r.ok ? r.json() : null)
              .then((data) => {
                if (!data) return;
                const findings = data.findings?.filter((f: { dismissed: boolean }) => !f.dismissed) ?? [];
                setScanSummary({
                  id: data.id,
                  score: data.score,
                  tier: data.tier,
                  findingsCount: findings.length,
                  criticalCount: findings.filter((f: { severity: string }) => f.severity === "critical").length,
                  highCount: findings.filter((f: { severity: string }) => f.severity === "high").length,
                });
              })
              .catch(() => {});
          }
        } else if (update.stage === "error") {
          es.close();
        }
      };
      es.onerror = () => {
        es.close();
        setScanState((s) => ({ ...s, stage: "error", message: "Соединение закрыто" }));
      };
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setScanState({ stage: "error", progress: 0, message: (err as Error).message });
      }
    }
  }, []);

  useEffect(() => {
    if (!scanning) return;
    const controller = new AbortController();
    abortRef.current = controller;
    runScan(scanning.address, scanning.network, controller.signal);
    return () => controller.abort();
  }, [scanning, runScan]);

  const isScanning = scanning !== null;

  return (
    <div className="flex h-full flex-col gap-0">
      {/* ═══ Compact Nav Bar (visible during scan) ═══ */}
      <div
        className={[
          "flex-shrink-0 overflow-hidden transition-all duration-500 ease-out",
          isScanning ? "max-h-[56px] opacity-100 mb-4" : "max-h-0 opacity-0",
        ].join(" ")}
      >
        <div className="h-[56px] flex items-center gap-4 px-5 rounded-xl border border-[#1a2e1a]/60 bg-[#080c08]">
          <button
            type="button"
            onClick={handleBack}
            className="flex items-center gap-2 text-sm text-[#6b8f6b] hover:text-[#4ade80] transition-colors"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Назад
          </button>
          <div className="h-5 w-px bg-[#1a2e1a]" />
          <span className="rounded-md border border-[#4ade80]/30 bg-[#4ade80]/10 px-2 py-0.5 font-mono text-xs uppercase text-[#4ade80]">
            {scanning?.network}
          </span>
          <span className="font-mono text-sm text-[#a8e6a8] truncate">
            {scanning ? shortAddr(scanning.address) : ""}
          </span>
          <div className="flex-1" />
          <ScanStageChip stage={scanState.stage} />
        </div>
      </div>

      {/* ═══ Main Content ═══ */}
      <div className="flex-1 min-h-0">
        <div className="grid h-full lg:grid-cols-[minmax(340px,480px)_1fr] gap-6">
          {/* ═══ Left Panel ═══ */}
          <div className="flex flex-col overflow-y-auto scrollbar-none py-1">
            {!isScanning ? (
              <div className="flex flex-col justify-center gap-5 flex-1">
                <div>
                  <h1 className="text-3xl lg:text-4xl font-extrabold leading-tight tracking-tight mb-3">
                    <span className="text-[#e2ffe2]">Аудит смарт-контрактов</span>
                    <br />
                    <span className="text-[#4ade80]">за 60 секунд</span>
                  </h1>
                  <p className="text-[#6b8f6b] text-sm leading-relaxed">
                    Выберите токен из live-ленты или вставьте адрес.
                  </p>
                </div>
                <ScanInput
                  address={selectedAddress}
                  network={selectedNetwork}
                  onAddressChange={setSelectedAddress}
                  onNetworkChange={setSelectedNetwork}
                  onScan={handleScan}
                />
              </div>
            ) : (
              <div className="flex flex-col gap-4 flex-1 animate-fade-in-up">
                {/* Timer + Stage header */}
                <ScanHeader stage={scanState.stage} scanStarted={scanning !== null} />

                {/* Progress bar */}
                <InlineProgress progress={scanState.progress} stage={scanState.stage} />

                {/* Stage stepper with descriptions */}
                <InlineStepper stage={scanState.stage} />

                {/* Error */}
                {scanState.stage === "error" && scanState.message && (
                  <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
                    {scanState.message}
                  </div>
                )}

                {/* Score result */}
                {scanState.stage === "done" && scanState.score !== undefined && (
                  <InlineScore score={scanState.score} />
                )}

                {/* Summary card with link to full report */}
                {scanSummary && (
                  <InlineSummary summary={scanSummary} />
                )}

                {/* New scan button */}
                {(scanState.stage === "done" || scanState.stage === "error") && (
                  <button
                    type="button"
                    onClick={handleBack}
                    className="w-full rounded-xl border border-[#1a2e1a] bg-[#0c120c] px-5 py-3 text-sm font-semibold text-[#a8e6a8] hover:border-[#4ade80]/30 hover:text-[#4ade80] transition-all"
                  >
                    Новый скан
                  </button>
                )}
              </div>
            )}
          </div>

          {/* ═══ Right Panel: Live Feed ═══ */}
          <div className="min-h-0 max-lg:min-h-[350px]">
            <LiveFeed onSelectToken={handleSelectToken} />
          </div>
        </div>
      </div>
    </div>
  );
}

function ScanStageChip({ stage }: { stage: Stage }) {
  const isError = stage === "error";
  const isDone = stage === "done";
  const current = STAGES.find((s) => s.id === stage);

  return (
    <span
      className={[
        "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold",
        isError
          ? "bg-red-500/10 text-red-400 border border-red-500/30"
          : isDone
            ? "bg-[#4ade80]/10 text-[#4ade80] border border-[#4ade80]/30"
            : "bg-[#4ade80]/5 text-[#a8e6a8] border border-[#1a2e1a]",
      ].join(" ")}
    >
      {!isDone && !isError && (
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#4ade80] opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-[#4ade80]" />
        </span>
      )}
      {current?.label ?? stage}
    </span>
  );
}

function ScanHeader({ stage, scanStarted }: { stage: Stage; scanStarted: boolean }) {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(Date.now());

  useEffect(() => {
    if (!scanStarted) return;
    startRef.current = Date.now();
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [scanStarted]);

  const isDone = stage === "done";
  const isError = stage === "error";
  const current = STAGES.find((s) => s.id === stage);
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const timeStr = minutes > 0
    ? `${minutes}:${seconds.toString().padStart(2, "0")}`
    : `${seconds}с`;

  return (
    <div className="rounded-xl border border-[#1a2e1a]/60 bg-[#0a0e0a] p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {!isDone && !isError && (
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#4ade80] opacity-60" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#4ade80]" />
            </span>
          )}
          {isDone && <span className="text-[#4ade80]">✓</span>}
          {isError && <span className="text-red-400">✕</span>}
          <span className="text-sm font-bold text-[#d4ffd4]">
            {isDone ? "Аудит завершён" : isError ? "Ошибка" : "Сканирование..."}
          </span>
        </div>
        <span className="font-mono text-lg font-bold tabular-nums text-[#4ade80]">
          {timeStr}
        </span>
      </div>
      {current && !isDone && !isError && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-[#6b8f6b]">{current.desc}</p>
          {current.estimate && (
            <span className="text-xs text-[#3d5c3d] tabular-nums">{current.estimate}</span>
          )}
        </div>
      )}
    </div>
  );
}

function InlineProgress({ progress, stage }: { progress: number; stage: Stage }) {
  const isError = stage === "error";
  const pct = Math.min(100, Math.max(0, progress));

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-[#547654]">Общий прогресс</span>
        <span className="font-mono text-xs font-bold tabular-nums text-[#a8e6a8]">{Math.round(pct)}%</span>
      </div>
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-[#0a0e0a] border border-[#1a2e1a]/60">
        <div
          className={[
            "absolute inset-y-0 left-0 rounded-full transition-all duration-700 ease-out",
            isError
              ? "bg-gradient-to-r from-red-600 to-red-400"
              : "bg-gradient-to-r from-emerald-600 via-[#4ade80] to-[#d4ffd4] shadow-[0_0_12px_rgba(74,222,128,0.3)]",
          ].join(" ")}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function InlineStepper({ stage }: { stage: Stage }) {
  const currentIdx = stage === "error" ? -1 : STAGES.findIndex((s) => s.id === stage);

  return (
    <div className="space-y-1">
      {STAGES.filter((s) => s.id !== "done").map((s, i) => {
        const isDone = currentIdx > i;
        const isCurrent = currentIdx === i;

        return (
          <div
            key={s.id}
            className={[
              "flex items-center gap-3 rounded-lg px-3 py-2 transition-all duration-300",
              isCurrent && stage !== "error"
                ? "bg-[#4ade80]/5 border border-[#4ade80]/20"
                : isCurrent && stage === "error"
                  ? "bg-red-500/5 border border-red-500/20"
                  : "border border-transparent",
            ].join(" ")}
          >
            {/* Step indicator */}
            <div
              className={[
                "flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold transition-all",
                isDone
                  ? "bg-[#4ade80]/20 text-[#4ade80]"
                  : isCurrent
                    ? "bg-[#4ade80] text-[#060a06] shadow-[0_0_12px_rgba(74,222,128,0.3)]"
                    : "bg-[#1a2e1a]/50 text-[#3d5c3d]",
              ].join(" ")}
            >
              {isDone ? "✓" : i + 1}
            </div>

            {/* Label */}
            <span
              className={[
                "text-sm font-medium flex-1 transition-colors",
                isDone
                  ? "text-[#4ade80]/70"
                  : isCurrent
                    ? "text-[#d4ffd4]"
                    : "text-[#3d5c3d]",
              ].join(" ")}
            >
              {s.label}
            </span>

            {/* Status */}
            {isDone && (
              <span className="text-xs text-[#4ade80]/50">готово</span>
            )}
            {isCurrent && stage !== "error" && (
              <span className="flex items-center gap-1.5 text-xs text-[#a8e6a8]">
                <span className="inline-block h-1 w-1 rounded-full bg-[#4ade80] animate-pulse" />
                в процессе
              </span>
            )}
            {isCurrent && stage === "error" && (
              <span className="text-xs text-red-400">ошибка</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function InlineScore({ score }: { score: number }) {
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    let frame: number;
    const duration = 1200;
    const start = performance.now();
    function animate(now: number) {
      const elapsed = now - start;
      const p = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplayed(Math.round(eased * score));
      if (p < 1) frame = requestAnimationFrame(animate);
    }
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [score]);

  const color =
    score >= 90 ? "#60a5fa" : score >= 70 ? "#4ade80" : score >= 40 ? "#facc15" : "#f87171";

  return (
    <div className="flex items-center gap-6 rounded-xl border border-[#1a2e1a]/60 bg-[#0a0e0a] p-6 animate-fade-in-up">
      <div className="relative h-20 w-20 flex-shrink-0">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="50" fill="none" stroke="#1a2e1a" strokeWidth="8" />
          <circle
            cx="60" cy="60" r="50" fill="none"
            stroke={color} strokeWidth="8" strokeLinecap="round"
            strokeDasharray={2 * Math.PI * 50}
            strokeDashoffset={2 * Math.PI * 50 - (displayed / 100) * 2 * Math.PI * 50}
            style={{ transition: "stroke-dashoffset 0.3s ease-out" }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-black tabular-nums" style={{ color }}>{displayed}</span>
        </div>
      </div>
      <div>
        <p className="text-sm font-semibold text-[#d4ffd4]">Security Score</p>
        <p className="text-xs text-[#547654] mt-1">из 100</p>
      </div>
    </div>
  );
}

function InlineSummary({ summary }: { summary: ScanSummary }) {
  const hasIssues = summary.criticalCount > 0 || summary.highCount > 0;

  return (
    <div className="rounded-xl border border-[#1a2e1a]/60 bg-[#0a0e0a] p-5 animate-fade-in-up space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-[#d4ffd4]">Результат аудита</p>
        <span className="text-xs text-[#547654]">
          {summary.findingsCount} находок
        </span>
      </div>

      {hasIssues && (
        <div className="flex gap-3">
          {summary.criticalCount > 0 && (
            <span className="rounded-md border border-red-500/30 bg-red-500/10 px-2.5 py-1 text-xs font-bold text-red-400">
              {summary.criticalCount} CRITICAL
            </span>
          )}
          {summary.highCount > 0 && (
            <span className="rounded-md border border-orange-500/30 bg-orange-500/10 px-2.5 py-1 text-xs font-bold text-orange-400">
              {summary.highCount} HIGH
            </span>
          )}
        </div>
      )}

      <Link
        href={`/scan/${summary.id}`}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#4ade80] px-5 py-3 text-sm font-bold text-[#060a06] transition-all hover:bg-[#6ee7a0] hover:shadow-[0_0_24px_rgba(74,222,128,0.3)]"
      >
        Открыть полный отчёт
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </Link>
    </div>
  );
}
