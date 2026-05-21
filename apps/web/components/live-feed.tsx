"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/* ───────── Types ───────── */

type FeedToken = {
  address: string;
  chain: string;
  network: string;
  name: string;
  symbol: string;
  priceUsd: string;
  priceChange24h: number;
  liquidity: number;
  volume24h: number;
  pairCount: number;
  url: string;
};

/* ───────── Chain mapping ───────── */

const CHAIN_TO_NETWORK: Record<string, string> = {
  ethereum: "ethereum",
  base: "base",
  arbitrum: "arbitrum",
  bsc: "bsc",
  solana: "solana",
};

const CHAIN_LABELS: Record<string, string> = {
  ethereum: "ETH",
  base: "BASE",
  arbitrum: "ARB",
  bsc: "BSC",
  solana: "SOL",
};

const SUPPORTED_CHAINS = new Set(Object.keys(CHAIN_TO_NETWORK));

/* ───────── Formatting ───────── */

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
  const str = n.toFixed(18);
  const m = str.match(/^0\.(0+)/);
  if (m && m[1].length >= 4) {
    const zeros = m[1].length;
    const sig = n.toFixed(zeros + 2).replace(/^0\.0+/, "");
    return `$0.0₍${zeros}₎${sig.slice(0, 3)}`;
  }
  return `$${n.toFixed(6)}`;
}

function shortAddr(a: string): string {
  if (a.length <= 12) return a;
  return `${a.slice(0, 6)}…${a.slice(-4)}`;
}

/* ───────── Fetch ───────── */

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
    }> = await res.json();

    const supported = profiles.filter((p) => SUPPORTED_CHAINS.has(p.chainId));
    if (supported.length === 0) return [];

    const byChain: Record<string, string[]> = {};
    for (const p of supported.slice(0, 20)) {
      const arr = byChain[p.chainId] || [];
      arr.push(p.tokenAddress);
      byChain[p.chainId] = arr;
    }

    const tokens: FeedToken[] = [];

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
          url: string;
        }> = await pairRes.json();

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
          });
        }
      } catch {
        /* ignore per-chain errors */
      }
    });

    await Promise.all(fetches);
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
    intervalRef.current = setInterval(load, 30_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [load]);

  const filtered =
    filterChain === "all"
      ? tokens
      : tokens.filter((t) => t.chain === filterChain);

  const chains = [...new Set(tokens.map((t) => t.chain))];

  return (
    <div className="flex h-full flex-col rounded-2xl border border-[#1a2e1a]/60 bg-[#080c08] overflow-hidden">
      {/* ─── Header ─── */}
      <div className="flex-shrink-0 flex items-center justify-between border-b border-[#1a2e1a]/40 px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#4ade80] opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#4ade80]" />
          </span>
          <span className="text-sm font-bold text-[#a8e6a8]">
            Live Blockchain
          </span>
        </div>
        <span className="text-xs text-[#3d5c3d] tabular-nums">
          {tokens.length} токенов
        </span>
      </div>

      {/* ─── Chain filter ─── */}
      <div className="flex-shrink-0 flex gap-1.5 border-b border-[#1a2e1a]/30 px-4 py-2.5 overflow-x-auto scrollbar-none">
        <ChainChip
          label="Все"
          active={filterChain === "all"}
          onClick={() => setFilterChain("all")}
        />
        {chains.map((c) => (
          <ChainChip
            key={c}
            label={CHAIN_LABELS[c] ?? c}
            active={filterChain === c}
            onClick={() => setFilterChain(c)}
          />
        ))}
      </div>

      {/* ─── Token list ─── */}
      <div className="flex-1 overflow-y-auto scrollbar-none">
        {loading ? (
          <div className="flex flex-col gap-1 p-2.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="flex items-center gap-3 rounded-xl px-3.5 py-3"
                style={{ animationDelay: `${i * 100}ms` }}
              >
                <div className="h-10 w-10 flex-shrink-0 rounded-xl bg-[#0c120c] animate-shimmer bg-gradient-to-r from-[#0c120c] via-[#1a2e1a]/30 to-[#0c120c]" />
                <div className="flex flex-1 flex-col gap-1.5">
                  <div className="h-3.5 w-24 rounded bg-[#0c120c] animate-shimmer bg-gradient-to-r from-[#0c120c] via-[#1a2e1a]/30 to-[#0c120c]" />
                  <div className="h-2.5 w-32 rounded bg-[#0c120c] animate-shimmer bg-gradient-to-r from-[#0c120c] via-[#1a2e1a]/30 to-[#0c120c]" />
                </div>
                <div className="flex flex-col items-end gap-1.5">
                  <div className="h-3.5 w-16 rounded bg-[#0c120c] animate-shimmer bg-gradient-to-r from-[#0c120c] via-[#1a2e1a]/30 to-[#0c120c]" />
                  <div className="h-2.5 w-10 rounded bg-[#0c120c] animate-shimmer bg-gradient-to-r from-[#0c120c] via-[#1a2e1a]/30 to-[#0c120c]" />
                </div>
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex h-full items-center justify-center p-8">
            <p className="text-sm text-[#3d5c3d]">Нет токенов для этой сети</p>
          </div>
        ) : (
          <div className="flex flex-col gap-1 p-2.5">
            {filtered.map((t, i) => (
              <TokenCard
                key={`${t.chain}-${t.address}`}
                token={t}
                index={i}
                onSelect={onSelectToken}
              />
            ))}
          </div>
        )}
      </div>

      {/* ─── Footer ─── */}
      <div className="flex-shrink-0 border-t border-[#1a2e1a]/30 px-5 py-2.5 text-center">
        <p className="text-xs text-[#3d5c3d]">
          Данные: DexScreener · Обновление каждые 30с
        </p>
      </div>
    </div>
  );
}

/* ───────── Sub-components ───────── */

function ChainChip({
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
        "whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-semibold transition-all",
        active
          ? "bg-[#4ade80] text-[#060a06] shadow-[0_0_10px_rgba(74,222,128,0.25)]"
          : "bg-transparent text-[#3d5c3d] hover:text-[#6b8f6b] hover:bg-[#0c120c]",
      ].join(" ")}
    >
      {label}
    </button>
  );
}

function TokenCard({
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
      className="group flex items-center gap-3 rounded-xl px-3.5 py-3 text-left transition-all hover:bg-[#0f1a0f] active:scale-[0.995] animate-fade-in-up"
      style={{ animationDelay: `${index * 30}ms`, animationFillMode: "both" }}
      title={`Сканировать ${t.symbol} (${t.network})`}
    >
      {/* Chain badge */}
      <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-[#0c120c] border border-[#1a2e1a]/40 text-[11px] font-bold text-[#3d5c3d] group-hover:border-[#4ade80]/20 group-hover:text-[#4ade80] transition-colors">
        {CHAIN_LABELS[t.chain] ?? t.chain.slice(0, 3).toUpperCase()}
      </div>

      {/* Token info */}
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-[#d4ffd4] group-hover:text-[#4ade80] transition-colors truncate">
            {t.symbol}
          </span>
          <span className="text-xs text-[#3d5c3d] truncate">{t.name}</span>
        </div>
        <span className="font-mono text-xs text-[#3d5c3d]">
          {shortAddr(t.address)}
        </span>
      </div>

      {/* Price + 24h change */}
      <div className="flex flex-col items-end flex-shrink-0 gap-0.5">
        <span className="font-mono text-sm text-[#a8e6a8]">
          {fmtPrice(t.priceUsd)}
        </span>
        <span
          className={`font-mono text-xs font-bold ${positive ? "text-[#4ade80]" : "text-[#f87171]"}`}
        >
          {positive ? "↑" : "↓"} {Math.abs(t.priceChange24h).toFixed(1)}%
        </span>
      </div>

      {/* Liquidity */}
      <div className="hidden xl:flex flex-col items-end flex-shrink-0 gap-0.5">
        <span className="text-xs text-[#3d5c3d]">Liquidity</span>
        <span className="font-mono text-xs text-[#6b8f6b] font-semibold">
          {fmtUsd(t.liquidity)}
        </span>
      </div>

      {/* Scan arrow */}
      <div className="flex-shrink-0 w-8 flex items-center justify-center">
        <svg
          className="h-5 w-5 text-[#1a2e1a] group-hover:text-[#4ade80] transition-all group-hover:translate-x-0.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </button>
  );
}
