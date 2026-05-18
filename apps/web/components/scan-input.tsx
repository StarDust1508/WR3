"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

const NETWORKS = [
  { id: "ethereum", label: "Ethereum" },
  { id: "base", label: "Base" },
  { id: "arbitrum", label: "Arbitrum" },
  { id: "bsc", label: "BSC" },
  { id: "solana", label: "Solana" },
] as const;

type NetworkId = (typeof NETWORKS)[number]["id"];

function isLikelyAddress(s: string): boolean {
  const t = s.trim();
  if (/^0x[a-fA-F0-9]{40}$/.test(t)) return true;
  if (/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(t)) return true;
  return false;
}

interface ScanInputProps {
  initialAddress?: string;
  initialNetwork?: string;
}

export function ScanInput({ initialAddress, initialNetwork }: ScanInputProps = {}) {
  const [address, setAddress] = useState(initialAddress ?? "");
  const [network, setNetwork] = useState<NetworkId>(
    (initialNetwork as NetworkId) ?? "ethereum"
  );
  const [error, setError] = useState<string | null>(null);
  const [isFocused, setFocused] = useState(false);
  const [shake, setShake] = useState(false);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  // Update from external selection (e.g. LiveFeed click)
  useEffect(() => {
    if (initialAddress) setAddress(initialAddress);
  }, [initialAddress]);
  useEffect(() => {
    if (initialNetwork) setNetwork(initialNetwork as NetworkId);
  }, [initialNetwork]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = address.trim();
    if (!trimmed) return;
    if (!isLikelyAddress(trimmed)) {
      setError("Неверный формат. Ожидается 0x… (40 hex) для EVM или base58 для Solana.");
      setShake(true);
      setTimeout(() => setShake(false), 600);
      return;
    }
    startTransition(() => {
      router.push(`/scan?address=${encodeURIComponent(trimmed)}&network=${network}`);
    });
  }

  const ready = address.trim().length > 0 && !isPending;

  return (
    <form
      onSubmit={handleSubmit}
      className={[
        "relative flex flex-col gap-4 rounded-2xl p-5 md:p-6",
        "bg-[rgba(16,24,16,0.6)] backdrop-blur-xl saturate-[1.4]",
        "border transition-all duration-300 ease-out",
        "shadow-[0_4px_24px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(74,222,128,0.05)]",
        isFocused
          ? "border-[var(--color-primary)] shadow-[0_0_0_4px_rgba(74,222,128,0.08),0_8px_32px_-8px_rgba(74,222,128,0.2)]"
          : "border-[var(--color-border)]",
        shake ? "animate-[shake_0.5s_ease-in-out]" : "",
      ].join(" ")}
    >
      {/* Animated gradient border glow overlay */}
      <div
        className={[
          "pointer-events-none absolute -inset-px rounded-2xl transition-opacity duration-300",
          "bg-[conic-gradient(from_var(--angle,0deg),transparent_60%,rgba(74,222,128,0.4)_80%,transparent_100%)]",
          isFocused ? "opacity-100 animate-[spin_3s_linear_infinite]" : "opacity-0",
        ].join(" ")}
        style={{ mask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)", maskComposite: "exclude", padding: "1px", borderRadius: "16px" }}
      />

      <label
        htmlFor="scan-address"
        className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8bb88b]"
      >
        Адрес контракта
      </label>

      <input
        id="scan-address"
        type="text"
        value={address}
        onChange={(e) => setAddress(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder="0xA0b8…6eB48 или base58"
        aria-label="Адрес контракта"
        autoComplete="off"
        spellCheck={false}
        className={[
          "w-full rounded-lg border bg-[var(--color-bg)] px-3.5 py-3",
          "font-mono text-base text-[#d4ffd4] placeholder:text-[#547654]",
          "outline-none transition-all duration-200",
          "caret-[var(--color-primary)]",
          isFocused
            ? "border-[var(--color-primary)]/40 shadow-[0_0_12px_rgba(74,222,128,0.1)]"
            : "border-[#547654]/50",
        ].join(" ")}
      />

      <div>
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#8bb88b]">
          Сеть
        </p>
        <div className="flex flex-wrap gap-2">
          {NETWORKS.map((n) => {
            const active = network === n.id;
            return (
              <button
                key={n.id}
                type="button"
                onClick={() => setNetwork(n.id)}
                aria-pressed={active}
                className={[
                  "relative min-h-[36px] rounded-lg border px-3.5 py-2 text-[13px] font-medium",
                  "transition-all duration-200 ease-out cursor-pointer",
                  active
                    ? "border-[var(--color-primary)] bg-[var(--color-primary)] text-[#0a0e0a] font-bold shadow-[0_0_12px_rgba(74,222,128,0.3)]"
                    : "border-[#547654]/60 bg-transparent text-[#8bb88b] hover:border-[var(--color-primary)]/50 hover:text-[#d4ffd4]",
                ].join(" ")}
              >
                {active && (
                  <span className="absolute inset-0 rounded-lg bg-[var(--color-primary)]/20 animate-ping" />
                )}
                <span className="relative">{n.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <button
        type="submit"
        disabled={isPending || !address.trim()}
        className={[
          "relative min-h-[48px] rounded-lg px-5 py-3 text-sm font-bold",
          "transition-all duration-200 ease-out",
          "disabled:cursor-not-allowed",
          !address.trim()
            ? "bg-[var(--color-primary)]/30 text-[#0a0e0a]/60 opacity-40"
            : isPending
              ? "bg-[var(--color-primary)]/70 text-[#0a0e0a] opacity-70"
              : "bg-[var(--color-primary)] text-[#0a0e0a] hover:brightness-110 active:scale-[0.98]",
          ready ? "animate-pulse-glow shadow-[0_0_20px_rgba(74,222,128,0.3)]" : "",
        ].join(" ")}
      >
        {isPending ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Запускаем...
          </span>
        ) : (
          "Запустить аудит"
        )}
      </button>

      {error && (
        <p
          role="alert"
          className="rounded-md border border-red-500/30 bg-red-500/8 px-3 py-2 text-xs leading-relaxed text-red-400"
        >
          {error}
        </p>
      )}
    </form>
  );
}
