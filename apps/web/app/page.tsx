import Link from "next/link";
import { ScanInput } from "@/components/scan-input";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col px-6 py-16">
      <header className="mb-16 flex items-center justify-between">
        <Link href="/" className="text-2xl font-bold tracking-tight">
          wr3
        </Link>
        <nav className="flex gap-6 text-sm text-zinc-600 dark:text-zinc-400">
          <Link href="/leaderboard" className="hover:text-zinc-900 dark:hover:text-zinc-50">
            Leaderboard
          </Link>
          <Link href="/pricing" className="hover:text-zinc-900 dark:hover:text-zinc-50">
            Pricing
          </Link>
          <Link href="/docs" className="hover:text-zinc-900 dark:hover:text-zinc-50">
            Docs
          </Link>
          <Link
            href="/auth/signin"
            className="rounded-md bg-zinc-900 px-3 py-1 text-white dark:bg-zinc-50 dark:text-zinc-900"
          >
            Sign in
          </Link>
        </nav>
      </header>

      <section className="flex flex-col gap-6">
        <h1 className="text-balance text-5xl font-bold leading-tight tracking-tight md:text-6xl">
          Audit your smart contract in 90 seconds.
        </h1>
        <p className="max-w-2xl text-pretty text-lg text-zinc-600 dark:text-zinc-400">
          AI-powered security analysis for EVM (Ethereum, Base, Arbitrum, BSC) and Solana. Built
          for vibe-coders and teams of 1–5 who can't afford a $25k CertiK audit.
        </p>

        <ScanInput />

        <p className="text-sm text-zinc-500">
          Free tier: 1 contract / 24h, preliminary score. Paid tier from $29/mo for unlimited and
          full Foundry PoCs.{" "}
          <Link href="/pricing" className="underline">
            See pricing →
          </Link>
        </p>
      </section>

      <section className="mt-24 grid gap-8 md:grid-cols-3">
        <Feature title="Multi-engine consensus" body="Aderyn + Wake + Slither + Medusa + ItyFuzz + Trident (Solana) + Certora (premium). One pipeline, cross-checked findings." />
        <Feature title="Transparent scoring" body="0–100 score on 5 axes with published weights. No black-box, no pay-to-play. The opposite of CertiK Skynet." />
        <Feature title="Solana, first-class" body="Most AI auditors are EVM-only. We treat Solana as P0 — Trident fuzzer, Sealevel-attacks RAG, Certora Solana support." />
      </section>

      <footer className="mt-32 border-t border-zinc-200 pt-8 text-sm text-zinc-500 dark:border-zinc-800">
        <div className="flex justify-between">
          <span>© 2026 wr3</span>
          <div className="flex gap-4">
            <Link href="/legal/tos">Terms</Link>
            <Link href="/legal/privacy">Privacy</Link>
            <Link href="https://github.com/StarDust1508/WR3">GitHub</Link>
          </div>
        </div>
        <p className="mt-4 max-w-3xl text-pretty text-xs text-zinc-400">
          AI-assisted audit results are best-effort and not a replacement for human review. wr3
          provides no warranty. Liability is capped at the cost of the audit. See full disclaimer
          in Terms.
        </p>
      </footer>
    </main>
  );
}

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-6 dark:border-zinc-800">
      <h3 className="mb-2 font-semibold">{title}</h3>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">{body}</p>
    </div>
  );
}
