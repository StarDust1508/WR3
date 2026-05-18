"use client";

import Link from "next/link";
import { useState } from "react";

import { LiveFeed } from "@/components/live-feed";
import { ScanInput } from "@/components/scan-input";

export function HeroWithFeed() {
  const [selectedAddress, setSelectedAddress] = useState("");
  const [selectedNetwork, setSelectedNetwork] = useState("ethereum");

  function handleSelectToken(address: string, network: string) {
    setSelectedAddress(address);
    setSelectedNetwork(network);
    // Scroll to scan input on mobile
    document.getElementById("scan-section")?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <section className="pt-12 pb-20 animate-fade-in-up">
      <div className="grid lg:grid-cols-[1fr,380px] gap-8 items-start">
        {/* Left — Hero + Scan Input */}
        <div id="scan-section" className="pt-4">
          <p className="font-mono text-xs text-[#547654] uppercase tracking-[0.2em] mb-6">
            AI Security Audit Engine
          </p>

          <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold leading-[1.05] tracking-tight mb-6">
            <span className="text-gradient">Найдите уязвимости</span>
            <br />
            <span className="text-[#d4ffd4]">до того, как их найдёт</span>
            <br />
            <span className="text-[#4ade80]">атакующий.</span>
          </h1>

          <p className="text-[#8bb88b] text-base md:text-lg leading-relaxed max-w-xl mb-8">
            От адреса контракта до полного отчёта за минуту.
            Или выберите токен из live-ленты справа.
          </p>

          <div className="max-w-xl">
            <ScanInput
              initialAddress={selectedAddress}
              initialNetwork={selectedNetwork}
            />
          </div>

          <p className="text-[#547654] text-xs mt-5">
            Free — 1 контракт в сутки.{" "}
            <Link
              href="/pricing"
              className="text-[#4ade80] underline underline-offset-2 hover:text-[#d4ffd4]"
            >
              Тарифы
            </Link>
          </p>
        </div>

        {/* Right — Live Blockchain Feed */}
        <div className="hidden lg:block h-[600px] sticky top-24">
          <LiveFeed onSelectToken={handleSelectToken} />
        </div>

        {/* Mobile: collapsible feed below scan input */}
        <div className="lg:hidden">
          <MobileFeedToggle onSelectToken={handleSelectToken} />
        </div>
      </div>
    </section>
  );
}

function MobileFeedToggle({
  onSelectToken,
}: {
  onSelectToken: (address: string, network: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-center gap-2 rounded-xl border border-[rgba(74,222,128,0.15)] bg-[rgba(10,14,10,0.6)] px-4 py-3 text-xs font-medium text-[#4ade80] transition-all hover:bg-[rgba(74,222,128,0.05)]"
      >
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#4ade80] opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-[#4ade80]" />
        </span>
        {open ? "Скрыть Live Feed" : "Показать Live Feed — токены в реальном времени"}
        <svg
          className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="mt-3 h-[400px]">
          <LiveFeed onSelectToken={onSelectToken} />
        </div>
      )}
    </div>
  );
}
