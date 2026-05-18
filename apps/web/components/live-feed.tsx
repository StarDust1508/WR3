"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/* ───────── Types ───────── */

type FeedToken = {
  address: string;
  chain: string;
  network: string; // wr3 network id
  name: string;
  symbol: string;
  priceUsd: string;
  priceChange24h: number;
  liquidity: number;
  volume24h: number;
  pairCount: number;
  url: string;
  age: string;
};

/* ───────── DexScreener chain → wr3 network mapping ───────── */

const CHAIN_TO_NETWORK: Record<string, string> = {
  ethereum: "ethereum",
  base: "base",
  arbitrum: "arbitrum",
  bsc: "bsc",
  solana: "solana",
};

const SUPPORTED_CHAINS = new Set(Object.keys(CHAIN_TO_NETWORK));

/* ───────── Formatting helpers ───────── */

function fmtUsd(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function fmtPrice(s: string): string {
  const n = parseFloat(s);
  if (!n || isNaN(n)) return "$0";
  if (n >= 1) return `$${n.toFixed(2)}`;
  if (n >= 0.01) return `$${n.toFixed(4)}`;
  // Count leading zeros after decimal
  const str = n.toFixed(18);
  const m = str.match(/^0\.(0+)/);
  if (m && m[1].length >= 4) {
    const zeros = m[1].length;
    const significant = n.toFixed(zeros + 2).replace(/^0\.0+/, "");
    return `$0.0{${zeros}}${significant.slice(0, 4)}`;
  }
  return `$${n.toFixed(6)}`;
}

function timeAgo(ms: number): string {
  const min = Math.floor(ms / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h`;
  return `${Math.floor(hr / 24)}d`;
}

/* ───────── Fetch from DexScreener ───────── */

async function fetchTrendingTokens(): Promise<FeedToken[]> {
  try {
    const res = await fetch(
      "https://api.dexscreener.com/token-profiles/latest/v1",
      { cache: "no-store" }
    );
    if (!res.ok) return [];
    const profiles: Array<{
      chainId: string;
      tokenAddress: string;
      url: string;
      description?: string;
    }> = await res.json();

    // Filter to supported chains
    const supported = profiles.filter((p) => SUPPORTED_CHAINS.has(p.chainId));
    if (supported.length === 0) return [];

    // Batch token addresses by chain for pair lookups
    const byChain: Record<string, string[]> = {};
    for (const p of supported.slice(0, 20)) {
      const arr = byChain[p.chainId] || [];
      arr.push(p.tokenAddress);
      byChain[p.chainId] = arr;
    }

    const tokens: FeedToken[] = [];

    // Fetch pair data per chain (DexScreener allows comma-separated addresses)
    const fetches = Object.entries(byChain).map(async ([chain, addrs]) => {
      try {
        const pairRes = await fetch(
          `https://api.dexscreener.com/tokens/v1/${chain}/${addrs.join(",")}`,
          { cache: "no-store" }
        );
        if (!pairRes.ok) return;
        const pairs: Array<{
          chainId: string;
          baseToken: { address: string; name: string; symbol: string };
          priceUsd: string;
          priceChange: { h24: number };
          liquidity: { usd: number };
          volume: { h24: number };
          pairCreatedAt: number;
          url: string;
        }> = await pairRes.json();

        // Group pairs by token address → pick best pair (highest liquidity)
        const best: Record<string, (typeof pairs)[0] & { pairCount: number }> = {};
        for (const pair of pairs) {
          const addr = pair.baseToken.address.toLowerCase();
          const existing = best[addr];
          if (!existing || (pair.liquidity?.usd ?? 0) > (existing.liquidity?.usd ?? 0)) {
            best[addr] = { ...pair, pairCount: 0 };
          }
          if (best[addr]) best[addr].pairCount++;
        }

        for (const [, pair] of Object.entries(best)) {
          tokens.push({
            address: pair.baseToken.address,
            chain: pair.chainId,
            network: CHAIN_TO_NETWORK[pair.chainId] ?? pair.chainId,
            name: pair.baseToken.name,
            symbol: pair.baseToken.symbol,
            priceUsd: pair.priceUsd ?? "0",
            priceChange24h: pair.priceChange?.h24 ?? 0,
            liquidity: pair.liquidity?.usd ?? 0,
            volume24h: pair.volume?.h24 ?? 0,
            pairCount: pair.pairCount,
            url: pair.url ?? "",
            age: pair.pairCreatedAt
              ? timeAgo(Date.now() - pair.pairCreatedAt)
              : "?",
          });
        }
      } catch {
        // Silently ignore per-chain errors
      }
    });

    await Promise.all(fetches);

    // Sort by liquidity descending
    tokens.sort((a, b) => b.liquidity - a.liquidity);
    return tokens;
  } catch {
    return [];
  }
}

/* ───────── Component ───────── */

interface LiveFeedProps {
  onSelectToken?: (address: string, network: string) => void;
}

export function LiveFeed({ onSelectToken }: LiveFeedProps) {
  const [tokens, setTokens] = useState<FeedToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterChain, setFilterChain] = useState<string>("all");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    const data = await fetchTrendingTokens();
    if (data.length > 0) setTokens(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    // Refresh every 30s
    intervalRef.current = setInterval(load, 30_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [load]);

  const filtered =
    filterChain === "all"
      ? tokens
      : tokens.filter((t) => t.chain === filterChain);

  const chains = [...new Set(tokens.map((t) => t.chain))];

  return (
    <div className="flex h-full flex-col rounded-2xl border border-[rgba(74,222,128,0.12)] bg-[rgba(10,14,10,0.8)] backdrop-blur-xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[rgba(74,222,128,0.08)] px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#4ade80] opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-[#4ade80]" />
          </span>
          <span className="font-mono text-xs font-bold uppercase tracking-wider text-[#4ade80]">
            Live Feed
          </span>
        </div>
        <span className="font-mono text-[10px] text-[#547654]">
          {tokens.length} tokens
        </span>
      </div>

      {/* Chain filter */}
      <div className="flex gap-1.5 overflow-x-auto border-b border-[rgba(74,222,128,0.06)] px-3 py-2 scrollbar-none">
        <FilterChip
          label="All"
          active={filterChain === "all"}
          onClick={() => setFilterChain("all")}
        />
        {chains.map((c) => (
          <FilterChip
            key={c}
            label={c.charAt(0).toUpperCase() + c.slice(1)}
            active={filterChain === c}
            onClick={() => setFilterChain(c)}
          />
        ))}
      </div>

      {/* Token list */}
      <div className="flex-1 overflow-y-auto scrollbar-none">
        {loading ? (
          <div className="flex flex-col gap-2 p-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-16 animate-pulse rounded-lg bg-[rgba(74,222,128,0.04)]"
                style={{ animationDelay: `${i * 100}ms` }}
              />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-6 text-center text-xs text-[#547654]">
            Нет токенов для этой сети
          </div>
        ) : (
          <div className="flex flex-col gap-1 p-2">
            {filtered.map((t, i) => (
              <TokenRow
                key={`${t.chain}-${t.address}`}
                token={t}
                index={i}
                onSelect={onSelectToken}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-[rgba(74,222,128,0.06)] px-4 py-2">
        <p className="text-center font-mono text-[9px] text-[#547654]">
          DexScreener · обновление каждые 30с · клик → аудит
        </p>
      </div>
    </div>
  );
}

/* ───────── Sub-components ───────── */

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "whitespace-nowrap rounded-md px-2.5 py-1 font-mono text-[10px] font-medium transition-all",
        active
          ? "bg-[#4ade80] text-[#0a0e0a] shadow-[0_0_8px_rgba(74,222,128,0.3)]"
          : "bg-transparent text-[#547654] hover:text-[#8bb88b]",
      ].join(" ")}
    >
      {label}
    </button>
  );
}

function TokenRow({
  token: t,
  index,
  onSelect,
}: {
  token: FeedToken;
  index: number;
  onSelect?: (address: string, network: string) => void;
}) {
  const positive = t.priceChange24h >= 0;

  return (
    <button
      type="button"
      onClick={() => onSelect?.(t.address, t.network)}
      className="group flex items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-all hover:bg-[rgba(74,222,128,0.06)] active:scale-[0.99] animate-fade-in-up"
      style={{ animationDelay: `${index * 40}ms`, animationFillMode: "both" }}
      title={`Scan ${t.symbol} on ${t.network}`}
    >
      {/* Rank / Chain icon */}
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-[rgba(74,222,128,0.06)] text-[10px] font-bold text-[#547654]">
        {t.chain.slice(0, 3).toUpperCase()}
      </div>

      {/* Name + address */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-xs font-semibold text-[#d4ffd4] group-hover:text-[#4ade80] transition-colors">
            {t.symbol}
          </span>
          <span className="truncate text-[10px] text-[#547654]">{t.name}</span>
        </div>
        <span className="font-mono text-[10px] text-[#547654]/70">
          {t.address.slice(0, 6)}…{t.address.slice(-4)}
        </span>
      </div>

      {/* Price + change */}
      <div className="flex flex-col items-end flex-shrink-0">
        <span className="font-mono text-[11px] text-[#8bb88b]">
          {fmtPrice(t.priceUsd)}
        </span>
        <span
          className={`font-mono text-[10px] font-bold ${positive ? "text-[#4ade80]" : "text-[#f87171]"}`}
        >
          {positive ? "+" : ""}
          {t.priceChange24h.toFixed(1)}%
        </span>
      </div>

      {/* Liquidity */}
      <div className="hidden sm:flex flex-col items-end flex-shrink-0">
        <span className="font-mono text-[10px] text-[#547654]">LIQ</span>
        <span className="font-mono text-[10px] text-[#8bb88b]">
          {fmtUsd(t.liquidity)}
        </span>
      </div>

      {/* Scan arrow */}
      <svg
        className="h-4 w-4 flex-shrink-0 text-[#547654] opacity-0 transition-all group-hover:opacity-100 group-hover:text-[#4ade80] group-hover:translate-x-0.5"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M13 7l5 5m0 0l-5 5m5-5H6"
        />
      </svg>
    </button>
  );
}
