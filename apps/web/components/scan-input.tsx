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
  const [shake, setShake] = useState(false);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

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
      setError("Неверный формат. Ожидается 0x… (EVM) или base58 (Solana).");
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
        "rounded-2xl border p-5 transition-all duration-300",
        "bg-[#0c120c] backdrop-blur-sm",
        "border-[#1a2e1a] hover:border-[#2a4e2a]",
        "shadow-[0_2px_20px_rgba(0,0,0,0.4)]",
        shake ? "animate-[shake_0.5s_ease-in-out]" : "",
      ].join(" ")}
    >
      {/* Address input */}
      <label
        htmlFor="scan-address"
        className="block text-xs font-semibold uppercase tracking-widest text-[#547654] mb-2"
      >
        Адрес контракта
      </label>

      <input
        id="scan-address"
        type="text"
        value={address}
        onChange={(e) => setAddress(e.target.value)}
        placeholder="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
        autoComplete="off"
        spellCheck={false}
        className={[
          "w-full rounded-xl border bg-[#060a06] px-4 py-3.5",
          "font-mono text-[15px] text-[#d4ffd4] placeholder:text-[#2a4e2a]",
          "outline-none transition-all duration-200",
          "focus:border-[#4ade80]/50 focus:shadow-[0_0_0_3px_rgba(74,222,128,0.08)]",
          "border-[#1a2e1a]",
        ].join(" ")}
      />

      {/* Network selector */}
      <div className="mt-4">
        <p className="text-xs font-semibold uppercase tracking-widest text-[#547654] mb-2">
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
                  "relative rounded-lg border px-4 py-2.5 text-sm font-medium",
                  "transition-all duration-200 cursor-pointer",
                  active
                    ? "border-[#4ade80] bg-[#4ade80] text-[#060a06] font-bold shadow-[0_0_16px_rgba(74,222,128,0.25)]"
                    : "border-[#1a2e1a] bg-transparent text-[#6b8f6b] hover:border-[#2a4e2a] hover:text-[#a8e6a8]",
                ].join(" ")}
              >
                {active && (
                  <span className="absolute inset-0 rounded-lg bg-[#4ade80]/20 animate-ping opacity-30" />
                )}
                <span className="relative">{n.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Submit button */}
      <button
        type="submit"
        disabled={isPending || !address.trim()}
        className={[
          "mt-4 w-full rounded-xl px-5 py-3.5 text-base font-bold",
          "transition-all duration-200",
          "disabled:cursor-not-allowed",
          !address.trim()
            ? "bg-[#1a2e1a]/50 text-[#3d5c3d] opacity-50"
            : isPending
              ? "bg-[#4ade80]/60 text-[#060a06]"
              : "bg-[#4ade80] text-[#060a06] hover:bg-[#6ee7a0] hover:shadow-[0_0_24px_rgba(74,222,128,0.3)] active:scale-[0.99]",
          ready ? "shadow-[0_0_20px_rgba(74,222,128,0.2)]" : "",
        ].join(" ")}
      >
        {isPending ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Запускаем анализ...
          </span>
        ) : (
          "Запустить аудит"
        )}
      </button>

      {error && (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-red-500/30 bg-red-500/8 px-4 py-2.5 text-sm text-red-400"
        >
          {error}
        </p>
      )}
    </form>
  );
}
