"use client";

import { useState } from "react";

import { LiveFeed } from "@/components/live-feed";
import { ScanInput } from "@/components/scan-input";

export function HeroWithFeed() {
  const [selectedAddress, setSelectedAddress] = useState("");
  const [selectedNetwork, setSelectedNetwork] = useState("ethereum");

  function handleSelectToken(address: string, network: string) {
    setSelectedAddress(address);
    setSelectedNetwork(network);
  }

  return (
    <div className="grid h-full lg:grid-cols-[1fr_420px] xl:grid-cols-[1fr_480px] gap-6">
      {/* ═══ Left Panel: Scan ═══ */}
      <div className="flex flex-col gap-5 overflow-y-auto scrollbar-none py-1">
        {/* Headline */}
        <div>
          <h1 className="text-3xl lg:text-4xl font-extrabold leading-tight tracking-tight mb-3">
            <span className="text-[#e2ffe2]">Аудит смарт-контрактов</span>
            <br />
            <span className="text-[#4ade80]">за 60 секунд</span>
          </h1>
          <p className="text-[#6b8f6b] text-base leading-relaxed max-w-lg">
            Выберите токен из live-ленты или вставьте адрес.
            AI проанализирует контракт по 5 осям безопасности.
          </p>
        </div>

        {/* Scan Input */}
        <ScanInput
          initialAddress={selectedAddress}
          initialNetwork={selectedNetwork}
        />

        {/* Info cards row */}
        <div className="grid grid-cols-3 gap-3">
          <InfoCard
            num="01"
            title="Статический анализ"
            desc="Slither + Aderyn + Wake параллельно"
          />
          <InfoCard
            num="02"
            title="AI-триаж"
            desc="4 LLM-агента фильтруют ложные срабатывания"
          />
          <InfoCard
            num="03"
            title="On-chain обогащение"
            desc="GoPlus · DeFiLlama · DexScreener · Etherscan"
          />
        </div>

        {/* Networks */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs text-[#3d5c3d] font-medium uppercase tracking-wider">Сети:</span>
          {["Ethereum", "Base", "Arbitrum", "BSC", "Solana"].map((n) => (
            <span
              key={n}
              className="flex items-center gap-1.5 rounded-full border border-[#1a2e1a] bg-[#0a0e0a] px-3 py-1 text-xs text-[#6b8f6b]"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-[#4ade80] shadow-[0_0_4px_rgba(74,222,128,0.5)]" />
              {n}
            </span>
          ))}
        </div>
      </div>

      {/* ═══ Right Panel: Live Feed ═══ */}
      <div className="min-h-0 hidden lg:block">
        <LiveFeed onSelectToken={handleSelectToken} />
      </div>

      {/* Mobile feed */}
      <div className="lg:hidden min-h-[350px]">
        <LiveFeed onSelectToken={handleSelectToken} />
      </div>
    </div>
  );
}

function InfoCard({ num, title, desc }: { num: string; title: string; desc: string }) {
  return (
    <div className="rounded-xl border border-[#1a2e1a]/60 bg-[#0a0e0a]/80 p-4 transition-all hover:border-[#4ade80]/20 hover:bg-[#0a0e0a]">
      <span className="font-mono text-lg font-black text-[#4ade80]/30">{num}</span>
      <p className="text-sm font-semibold text-[#c4f0c4] mt-1">{title}</p>
      <p className="text-xs text-[#547654] mt-1 leading-relaxed">{desc}</p>
    </div>
  );
}
