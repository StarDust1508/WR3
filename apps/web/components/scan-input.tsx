"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

const NETWORKS = [
  { id: "ethereum", label: "Ethereum" },
  { id: "base", label: "Base" },
  { id: "arbitrum", label: "Arbitrum" },
  { id: "bsc", label: "BSC" },
  { id: "solana", label: "Solana" },
] as const;

type NetworkId = (typeof NETWORKS)[number]["id"];

export function ScanInput() {
  const [address, setAddress] = useState("");
  const [network, setNetwork] = useState<NetworkId>("base");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmed = address.trim();
    if (!trimmed) {
      setError("Paste a contract address or verified source.");
      return;
    }

    startTransition(() => {
      router.push(`/scan?address=${encodeURIComponent(trimmed)}&network=${network}`);
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full flex-col gap-3 md:flex-row">
      <select
        value={network}
        onChange={(e) => setNetwork(e.target.value as NetworkId)}
        className="rounded-md border border-zinc-300 bg-white px-3 py-3 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        aria-label="Network"
      >
        {NETWORKS.map((n) => (
          <option key={n.id} value={n.id}>
            {n.label}
          </option>
        ))}
      </select>

      <input
        type="text"
        value={address}
        onChange={(e) => setAddress(e.target.value)}
        placeholder="0x... or paste source code"
        className="flex-1 rounded-md border border-zinc-300 bg-white px-4 py-3 text-base dark:border-zinc-700 dark:bg-zinc-900"
        aria-label="Contract address"
        autoComplete="off"
        spellCheck={false}
      />

      <button
        type="submit"
        disabled={isPending}
        className="rounded-md bg-zinc-900 px-6 py-3 font-medium text-white transition hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200"
      >
        {isPending ? "Loading…" : "Scan"}
      </button>

      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </form>
  );
}
