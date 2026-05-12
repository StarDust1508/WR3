"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

const NETWORKS = [
  { id: "ethereum", label: "eth" },
  { id: "base", label: "base" },
  { id: "arbitrum", label: "arb" },
  { id: "bsc", label: "bsc" },
  { id: "solana", label: "sol" },
] as const;

type NetworkId = (typeof NETWORKS)[number]["id"];

const PRIMARY = "#4ade80";
const BG = "#0a0e0a";
const MUTED = "#5a8a5a";
const DIM = "#3a5e3a";
const FG = "#a8e6a8";
const ERR = "#f87171";

export function ScanInput() {
  const [address, setAddress] = useState("");
  const [network, setNetwork] = useState<NetworkId>("ethereum");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = address.trim();
    if (!trimmed) {
      setError("вставь адрес контракта");
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
        background: "#0f1a0f",
        border: `1px solid ${DIM}`,
        borderRadius: 6,
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ color: PRIMARY, fontSize: 14, fontWeight: 700 }}>$</span>
        <input
          type="text"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="0x... либо base58"
          aria-label="Адрес контракта"
          autoComplete="off"
          spellCheck={false}
          style={{
            flex: 1,
            background: BG,
            border: `1px solid ${DIM}`,
            borderRadius: 4,
            padding: "10px 12px",
            fontSize: 13,
            color: FG,
            fontFamily: "inherit",
            outline: "none",
            minHeight: 44,
            caretColor: PRIMARY,
          }}
        />
      </div>

      <div style={{ display: "flex", gap: 6, paddingLeft: 22, flexWrap: "wrap" }}>
        {NETWORKS.map((n) => {
          const active = network === n.id;
          return (
            <button
              key={n.id}
              type="button"
              onClick={() => setNetwork(n.id)}
              style={{
                background: active ? PRIMARY : "transparent",
                color: active ? BG : MUTED,
                border: `1px solid ${active ? PRIMARY : DIM}`,
                borderRadius: 3,
                padding: "5px 10px",
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                fontFamily: "inherit",
                cursor: "pointer",
                minHeight: 28,
              }}
            >
              --{n.label}
            </button>
          );
        })}
      </div>

      <button
        type="submit"
        disabled={isPending}
        style={{
          background: PRIMARY,
          color: BG,
          border: `1px solid ${PRIMARY}`,
          borderRadius: 4,
          padding: "10px 16px",
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          fontFamily: "inherit",
          cursor: isPending ? "not-allowed" : "pointer",
          opacity: isPending ? 0.5 : 1,
          minHeight: 44,
        }}
      >
        $ {isPending ? "сканирую…" : "запустить аудит"}
      </button>

      {error && (
        <p role="alert" style={{ color: ERR, fontSize: 11, margin: 0 }}>
          <span>ERR </span>{error}
        </p>
      )}
    </form>
  );
}
