"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

const NETWORKS = [
  { id: "ethereum", label: "Ethereum" },
  { id: "base", label: "Base" },
  { id: "arbitrum", label: "Arbitrum" },
  { id: "bsc", label: "BSC" },
  { id: "solana", label: "Solana" },
] as const;

type NetworkId = (typeof NETWORKS)[number]["id"];

const PRIMARY = "#4ade80";
const BG = "#0a0e0a";
const HI = "#d4ffd4";
const MUTED = "#8bb88b";
const DIM = "#547654";
const ERR = "#f87171";

function isLikelyAddress(s: string): boolean {
  const t = s.trim();
  if (/^0x[a-fA-F0-9]{40}$/.test(t)) return true;
  if (/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(t)) return true;
  return false;
}

export function ScanInput() {
  const [address, setAddress] = useState("");
  const [network, setNetwork] = useState<NetworkId>("ethereum");
  const [error, setError] = useState<string | null>(null);
  const [isFocused, setFocused] = useState(false);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = address.trim();
    if (!trimmed) return; // button is disabled when empty — defence in depth
    if (!isLikelyAddress(trimmed)) {
      setError("Неверный формат. Ожидается 0x… (40 hex) для EVM или base58 для Solana.");
      return;
    }
    startTransition(() => {
      router.push(`/scan?address=${encodeURIComponent(trimmed)}&network=${network}`);
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        background:
          "linear-gradient(180deg, rgba(15,26,15,0.95) 0%, rgba(15,26,15,0.7) 100%)",
        border: `1px solid ${isFocused ? PRIMARY : DIM}`,
        borderRadius: 10,
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 16,
        // Focus halo — subtle outer glow when the input is active.
        boxShadow: isFocused
          ? "0 0 0 4px rgba(74, 222, 128, 0.08), 0 8px 32px -8px rgba(74, 222, 128, 0.20)"
          : "0 4px 24px -12px rgba(0, 0, 0, 0.6)",
        transition: "box-shadow 200ms ease, border-color 200ms ease",
      }}
    >
      <label
        htmlFor="scan-address"
        style={{
          color: MUTED,
          fontSize: 11,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          fontWeight: 600,
        }}
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
        style={{
          background: BG,
          border: `1px solid ${DIM}`,
          borderRadius: 6,
          padding: "12px 14px",
          // 16px on mobile prevents iOS zoom-on-focus.
          fontSize: 16,
          fontFamily: "var(--font-mono)",
          color: HI,
          outline: "none",
          minHeight: 48,
          caretColor: PRIMARY,
        }}
      />

      <div>
        <p
          style={{
            color: MUTED,
            fontSize: 11,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            fontWeight: 600,
            margin: "0 0 8px",
          }}
        >
          Сеть
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {NETWORKS.map((n) => {
            const active = network === n.id;
            return (
              <button
                key={n.id}
                type="button"
                onClick={() => setNetwork(n.id)}
                aria-pressed={active}
                style={{
                  background: active ? PRIMARY : "transparent",
                  color: active ? BG : MUTED,
                  border: `1px solid ${active ? PRIMARY : DIM}`,
                  borderRadius: 6,
                  padding: "8px 14px",
                  fontSize: 13,
                  fontWeight: active ? 700 : 500,
                  fontFamily: "var(--font-sans)",
                  cursor: "pointer",
                  minHeight: 36,
                  transition: "background 120ms ease, color 120ms ease",
                }}
              >
                {n.label}
              </button>
            );
          })}
        </div>
      </div>

      <button
        type="submit"
        disabled={isPending || !address.trim()}
        style={{
          background: PRIMARY,
          color: BG,
          border: "none",
          borderRadius: 6,
          padding: "12px 18px",
          fontSize: 14,
          fontWeight: 700,
          fontFamily: "var(--font-sans)",
          cursor: isPending || !address.trim() ? "not-allowed" : "pointer",
          opacity: !address.trim() ? 0.4 : isPending ? 0.7 : 1,
          minHeight: 48,
          transition: "opacity 150ms ease, transform 80ms ease",
        }}
      >
        {isPending ? "Запускаем…" : "Запустить аудит"}
      </button>

      {error && (
        <p
          role="alert"
          style={{
            color: ERR,
            fontSize: 12,
            margin: 0,
            padding: "8px 10px",
            background: "rgba(248,113,113,0.08)",
            border: "1px solid rgba(248,113,113,0.30)",
            borderRadius: 4,
            lineHeight: 1.5,
          }}
        >
          {error}
        </p>
      )}
    </form>
  );
}
