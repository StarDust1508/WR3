"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { getStoredToken } from "@/lib/tg-session";

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
    // Empty case is unreachable — button is disabled while field is empty.
    if (!isLikelyAddress(trimmed)) {
      setError(
        "Неверный формат адреса. Ожидается 0x… (40 hex) для EVM или base58 для Solana.",
      );
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
          let detail = `Не удалось запустить скан (HTTP ${res.status}).`;
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

  const isReady = !!address.trim() && !pending;

  return (
    <form
      onSubmit={submit}
      className="tg-card flex flex-col gap-3"
      style={{
        transition: "border-color 200ms ease, box-shadow 200ms ease",
      }}
    >
      <h2 className="tg-hint">Новый аудит</h2>

      <input
        type="text"
        value={address}
        onChange={(e) => setAddress(e.target.value)}
        placeholder="Адрес контракта"
        aria-label="Адрес контракта"
        className="tg-input"
        autoComplete="off"
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        inputMode="text"
        // 16px font-size prevents iOS Safari from zooming on focus.
        style={{ fontSize: 16 }}
      />

      <div
        className="flex gap-1.5 overflow-x-auto"
        style={{ scrollbarWidth: "none" }}
      >
        {NETWORKS.map((n) => {
          const active = network === n.id;
          return (
            <button
              key={n.id}
              type="button"
              onClick={() => setNetwork(n.id)}
              className={`tg-chip ${active ? "tg-ping" : ""}`}
              style={{
                background: active ? "var(--hb-primary)" : "transparent",
                color: active ? "var(--hb-bg)" : "var(--hb-text-dim)",
                border: active
                  ? "1px solid var(--hb-primary)"
                  : "1px solid var(--hb-border)",
                padding: "10px 14px",
                fontSize: 12,
                minHeight: 44,
                whiteSpace: "nowrap",
                cursor: "pointer",
                fontWeight: active ? 700 : 500,
                boxShadow: active
                  ? "0 0 12px rgba(74, 222, 128, 0.25)"
                  : "none",
                transition: "all 150ms ease",
              }}
            >
              {n.label}
            </button>
          );
        })}
      </div>

      <button
        type="submit"
        disabled={pending || !address.trim()}
        className={`tg-button tg-button-primary ${isReady ? "tg-btn-pulse" : ""}`}
        style={{
          marginTop: 4,
          position: "relative",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
        }}
      >
        {pending && <span className="tg-spinner" />}
        {pending ? "Запускаем…" : "Запустить аудит"}
      </button>

      {error && (
        <div
          role="alert"
          className="tg-shake"
          style={{
            background: "rgba(248, 113, 113, 0.06)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
            border: "1px solid rgba(248, 113, 113, 0.25)",
            borderRadius: 6,
            padding: "10px 12px",
            boxShadow: "0 0 12px rgba(248, 113, 113, 0.06)",
          }}
        >
          <p
            className="text-[11px] leading-relaxed"
            style={{ color: "var(--hb-error)" }}
          >
            {error}
          </p>
        </div>
      )}
    </form>
  );
}
