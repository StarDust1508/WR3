"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { getStoredToken } from "@/lib/tg-session";

const NETWORKS = [
  { id: "base", label: "Base" },
  { id: "ethereum", label: "Ethereum" },
  { id: "arbitrum", label: "Arbitrum" },
  { id: "bsc", label: "BSC" },
  { id: "solana", label: "Solana" },
] as const;

type NetworkId = (typeof NETWORKS)[number]["id"];

function isLikelyAddress(s: string): boolean {
  const t = s.trim();
  if (/^0x[a-fA-F0-9]{40}$/.test(t)) return true; // EVM
  if (/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(t)) return true; // Solana base58
  return false;
}

export function MiniAppScanForm() {
  const [address, setAddress] = useState("");
  const [network, setNetwork] = useState<NetworkId>("base");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  const canSubmit = isLikelyAddress(address) && !pending;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = address.trim();
    if (!trimmed) {
      setError("Paste a contract address.");
      return;
    }
    if (!isLikelyAddress(trimmed)) {
      setError("That doesn't look like an EVM (0x...) or Solana address.");
      return;
    }

    startTransition(async () => {
      try {
        const token = getStoredToken();
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (token) headers.Authorization = `Bearer ${token}`;

        const res = await fetch("/api/v1/scan", {
          method: "POST",
          headers,
          body: JSON.stringify({ address: trimmed, network }),
        });
        if (!res.ok) {
          let detail = `scan failed (${res.status})`;
          try {
            const body = (await res.json()) as { detail?: string };
            if (body?.detail) detail = body.detail;
          } catch {
            /* ignore */
          }
          throw new Error(detail);
        }
        const data = (await res.json()) as { job_id: string };
        router.push(`/tg/scan/job/${data.job_id}`);
      } catch (e) {
        setError((e as Error).message);
      }
    });
  }

  return (
    <form onSubmit={submit} className="tg-card flex flex-col gap-3">
      <h2 className="tg-hint">Quick scan</h2>

      <div className="relative">
        <Search
          size={16}
          color="var(--tg-hint)"
          aria-hidden
          style={{
            position: "absolute",
            left: 14,
            top: "50%",
            transform: "translateY(-50%)",
            pointerEvents: "none",
          }}
        />
        <input
          type="text"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="0x... or Solana address"
          className="tg-input"
          style={{ paddingLeft: 38 }}
          autoComplete="off"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          inputMode="text"
        />
      </div>

      <div
        className="flex gap-2 overflow-x-auto"
        style={{ scrollbarWidth: "none" }}
      >
        {NETWORKS.map((n) => {
          const active = network === n.id;
          return (
            <button
              key={n.id}
              type="button"
              onClick={() => setNetwork(n.id)}
              className="tg-chip"
              style={{
                background: active
                  ? "var(--tg-button)"
                  : "color-mix(in srgb, var(--tg-text) 8%, transparent)",
                color: active ? "var(--tg-button-text)" : "var(--tg-text)",
                padding: "8px 14px",
                fontSize: 13,
                textTransform: "none",
                letterSpacing: 0,
                fontWeight: 500,
                minHeight: 36,
                whiteSpace: "nowrap",
              }}
            >
              {n.label}
            </button>
          );
        })}
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        className="tg-button"
      >
        {pending ? "Scanning…" : "Scan"}
      </button>

      {error && (
        <p
          role="alert"
          className="text-sm"
          style={{ color: "var(--tg-destructive)" }}
        >
          {error}
        </p>
      )}
    </form>
  );
}
