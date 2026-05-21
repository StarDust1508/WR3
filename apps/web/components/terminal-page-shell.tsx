import Link from "next/link";
import type { ReactNode } from "react";

/**
 * Shared shell for non-Mini-App pages (landing, pricing, docs, legal).
 * Keeps the same brand aesthetic as /tg without re-implementing the
 * navigation on each page.
 */
export function TerminalPageShell({
  title,
  eyebrow,
  children,
}: {
  title: string;
  /** Optional small uppercase pre-headline shown above the H1. */
  eyebrow?: string;
  children: ReactNode;
}) {
  return (
    <main className="min-h-screen bg-[#060a06] font-sans px-6 pt-8 pb-16">
      <div className="mx-auto max-w-[960px]">
        {/* ─── Sticky Header ─── */}
        <header className="sticky top-0 z-50 -mx-6 px-6 py-4 mb-12 flex items-center justify-between flex-wrap gap-4 backdrop-blur-xl bg-[#060a06]/80 border-b border-[#1a2e1a]/60">
          <Link
            href="/"
            className="text-[#4ade80] font-bold text-lg border border-[#4ade80] px-3 py-1.5 rounded-lg font-mono no-underline hover:bg-[#4ade80]/10 transition-colors"
          >
            wr3
          </Link>
          <nav className="flex gap-6 text-sm items-center">
            <Link href="/incidents" className="text-[#8bb88b] no-underline hover:text-[#d4ffd4] transition-colors">
              Инциденты
            </Link>
            <Link href="/leaderboard" className="text-[#8bb88b] no-underline hover:text-[#d4ffd4] transition-colors">
              Лидерборд
            </Link>
            <Link href="/pricing" className="text-[#8bb88b] no-underline hover:text-[#d4ffd4] transition-colors">
              Тарифы
            </Link>
            <Link href="/docs" className="text-[#8bb88b] no-underline hover:text-[#d4ffd4] transition-colors hidden sm:block">
              Документация
            </Link>
            <a
              href="https://t.me/KitronBot"
              className="bg-[#4ade80] text-[#060a06] px-4 py-2 rounded-lg text-sm font-bold no-underline hover:shadow-[0_0_20px_rgba(74,222,128,0.3)] transition-shadow"
            >
              Открыть бот
            </a>
          </nav>
        </header>

        {/* ─── Eyebrow ─── */}
        {eyebrow && (
          <p className="text-[#547654] text-sm mb-3 tracking-widest uppercase font-mono">
            {eyebrow}
          </p>
        )}

        {/* ─── Title ─── */}
        <h1 className="text-3xl lg:text-4xl font-extrabold leading-[1.15] mb-8 tracking-tight text-[#e2ffe2]">
          {title}
        </h1>

        {/* ─── Content ─── */}
        <article className="rounded-2xl border border-[#1a2e1a]/60 bg-[#0c120c] p-8 text-[#a8e6a8] text-base leading-relaxed animate-fade-in-up">
          {children}
        </article>

        {/* ─── Footer ─── */}
        <footer className="mt-16 text-sm text-[#8bb88b] text-center">
          <Link href="/" className="text-[#8bb88b] no-underline hover:text-[#4ade80] transition-colors">
            &lsaquo; На главную
          </Link>
        </footer>
      </div>
    </main>
  );
}
