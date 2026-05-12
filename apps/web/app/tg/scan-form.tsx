"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { getStoredToken } from "@/lib/tg-session";

const NETWORKS = ["base", "ethereum", "arbitrum", "bsc", "solana"] as const;

export function MiniAppScanForm() {
  const [address, setAddress] = useState("");
  const [network, setNetwork] = useState<(typeof NETWORKS)[number]>("base");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = address.trim();
    if (!trimmed) {
      setError("Paste a contract address.");
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
          throw new Error(`scan failed (${res.status})`);
        }
        // We could subscribe to the SSE here; for the Mini App, simpler:
        // just open the report page, which lazy-loads as it becomes ready.
        const data = (await res.json()) as { job_id: string };
        router.push(`/tg/scan/job/${data.job_id}`);
      } catch (e) {
        setError((e as Error).message);
      }
    });
  }

  return (
    <form
      onSubmit={submit}
      className="space-y-2 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
        Quick scan
      </h2>
      <input
        type="text"
        value={address}
        onChange={(e) => setAddress(e.target.value)}
        placeholder="0x..."
        className="w-full rounded-md border border-zinc-300 bg-white px-3 py-3 text-base dark:border-zinc-700 dark:bg-zinc-900"
        autoComplete="off"
        spellCheck={false}
      />
      <div className="flex items-center gap-2">
        <select
          value={network}
          onChange={(e) => setNetwork(e.target.value as (typeof NETWORKS)[number])}
          className="flex-1 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
        >
          {NETWORKS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-50 dark:text-zinc-900"
        >
          {pending ? "…" : "Scan"}
        </button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </form>
  );
}
