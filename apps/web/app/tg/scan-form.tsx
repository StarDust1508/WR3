"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { getStoredToken } from "@/lib/tg-session";

const NETWORKS = [
  { id: "ethereum", label: "eth" },
  { id: "base", label: "base" },
  { id: "arbitrum", label: "arb" },
  { id: "bsc", label: "bsc" },
  { id: "solana", label: "sol" },
] as const;

type NetworkId = (typeof NETWORKS)[number]["id"];

function isLikelyAddress(s: string): boolean {
  const t = s.trim();
  if (/^0x[a-fA-F0-9]{40}$/.test(t)) return true;
  if (/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(t)) return true;
  return false;
}

export function MiniAppScanForm() {
  const [address, setAddress] = useState("");
  const [network, setNetwork] = useState<NetworkId>("ethereum");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = address.trim();
    if (!trimmed) {
      setError("вставь адрес контракта");
      return;
    }
    if (!isLikelyAddress(trimmed)) {
      setError("неверный формат адреса (нужен 0x... или base58)");
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
          let detail = `скан не запустился (${res.status})`;
          try {
            const body = (await res.json()) as { detail?: string };
            if (body?.detail) detail = body.detail;
          } catch { /* ignore */ }
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
      <h2 className="tg-hint">аудит -i</h2>

      <div className="flex items-center gap-2">
        <span style={{ color: "var(--hb-primary)", fontSize: 14 }}>$</span>
        <input
          type="text"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="0x... либо base58"
          className="tg-input"
          autoComplete="off"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          inputMode="text"
          style={{ flex: 1 }}
        />
      </div>

      <div
        className="flex gap-1.5 overflow-x-auto"
        style={{ scrollbarWidth: "none", paddingLeft: 18 }}
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
                background: active ? "var(--hb-primary)" : "transparent",
                color: active ? "var(--hb-bg)" : "var(--hb-text-dim)",
                border: active ? "1px solid var(--hb-primary)" : "1px solid var(--hb-border)",
                padding: "6px 12px",
                fontSize: 11,
                minHeight: 30,
                whiteSpace: "nowrap",
                cursor: "pointer",
              }}
            >
              --{n.label}
            </button>
          );
        })}
      </div>

      <button
        type="submit"
        disabled={pending || !address.trim()}
        className="tg-button tg-button-primary"
        style={{ marginTop: 4 }}
      >
        {pending ? "сканирую…" : "старт"}
      </button>

      {error && (
        <p role="alert" className="text-xs" style={{ color: "var(--hb-error)" }}>
          <span style={{ color: "var(--hb-error)" }}>ERR </span>{error}
        </p>
      )}
    </form>
  );
}
