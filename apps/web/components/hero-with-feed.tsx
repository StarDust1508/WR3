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
    <div className="grid h-full lg:grid-cols-[minmax(360px,480px)_1fr] gap-4">
      {/* ─── Left: Scan Panel ─── */}
      <div className="flex flex-col gap-4 overflow-y-auto scrollbar-none">
        {/* Scan Input */}
        <ScanInput
          initialAddress={selectedAddress}
          initialNetwork={selectedNetwork}
        />

        {/* How it works — compact */}
        <div className="glass-card p-4">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[#547654] mb-3">
            Как это работает
          </p>
          <div className="grid grid-cols-3 gap-3">
            <StepMini num="1" text="Выберите токен из ленты или вставьте адрес" />
            <StepMini num="2" text="AI анализ: статика + LLM + on-chain данные" />
            <StepMini num="3" text="Отчёт с уязвимостями, score и PoC" />
          </div>
        </div>

        {/* Engine badges */}
        <div className="flex flex-wrap gap-1.5">
          {["Slither", "Aderyn", "Wake", "LLM Triage", "GoPlus", "DeFiLlama", "DexScreener"].map(
            (engine) => (
              <span
                key={engine}
                className="rounded-md border border-[#547654]/30 bg-[rgba(10,14,10,0.6)] px-2 py-1 font-mono text-[9px] text-[#547654]"
              >
                {engine}
              </span>
            )
          )}
        </div>

        {/* Supported networks */}
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-[#547654] uppercase tracking-wider">Сети:</span>
          <div className="flex gap-1.5">
            {["ETH", "Base", "ARB", "BSC", "SOL"].map((n) => (
              <span
                key={n}
                className="flex items-center gap-1 rounded-md border border-[rgba(74,222,128,0.15)] bg-[rgba(74,222,128,0.04)] px-2 py-0.5 text-[10px] text-[#8bb88b]"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-[#4ade80]" />
                {n}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ─── Right: Live Feed (full height) ─── */}
      <div className="min-h-0 hidden lg:block">
        <LiveFeed onSelectToken={handleSelectToken} />
      </div>

      {/* ─── Mobile: Feed below ─── */}
      <div className="lg:hidden min-h-[300px]">
        <LiveFeed onSelectToken={handleSelectToken} />
      </div>
    </div>
  );
}

function StepMini({ num, text }: { num: string; text: string }) {
  return (
    <div className="flex flex-col items-center text-center gap-1.5">
      <span className="flex h-6 w-6 items-center justify-center rounded-full border border-[rgba(74,222,128,0.25)] bg-[rgba(74,222,128,0.06)] font-mono text-[10px] font-bold text-[#4ade80]">
        {num}
      </span>
      <span className="text-[10px] leading-tight text-[#547654]">{text}</span>
    </div>
  );
}
