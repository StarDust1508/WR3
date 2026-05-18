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
    <main className="min-h-screen font-sans px-6 pt-8 pb-16">
      <div className="mx-auto max-w-[880px]">
        {/* ─── Sticky Header ─── */}
        <header className="sticky top-0 z-50 -mx-6 px-6 py-4 mb-12 flex items-center justify-between flex-wrap gap-3 backdrop-blur-xl bg-[var(--color-bg)]/80 border-b border-[var(--color-border)]">
          <Link
            href="/"
            className="text-[var(--color-primary)] font-bold text-base border border-[var(--color-primary)] px-2.5 py-1 rounded font-mono no-underline hover:bg-[var(--color-primary)]/10 transition-colors"
          >
            wr3
          </Link>
          <nav className="flex gap-5 text-[13px] items-center">
            <Link href="/incidents" className="text-[#8bb88b] no-underline hover:text-[#d4ffd4] transition-colors">
              Инциденты
            </Link>
            <Link href="/leaderboard" className="text-[#8bb88b] no-underline hover:text-[#d4ffd4] transition-colors">
              Лидерборд
            </Link>
            <Link href="/pricing" className="text-[#8bb88b] no-underline hover:text-[#d4ffd4] transition-colors">
              Тарифы
            </Link>
            <Link href="/docs" className="text-[#8bb88b] no-underline hover:text-[#d4ffd4] transition-colors">
              Документация
            </Link>
            <a
              href="https://t.me/KitronBot"
              className="bg-[var(--color-primary)] text-[var(--color-bg)] px-3 py-1.5 rounded text-[11px] font-bold no-underline hover:shadow-[0_0_20px_rgba(74,222,128,0.3)] transition-shadow"
            >
              Открыть бот
            </a>
          </nav>
        </header>

        {/* ─── Eyebrow ─── */}
        {eyebrow && (
          <p className="text-[#547654] text-xs mb-2.5 tracking-widest uppercase font-mono">
            {eyebrow}
          </p>
        )}

        {/* ─── Title ─── */}
        <h1 className="text-[clamp(28px,4.5vw,40px)] font-extrabold leading-[1.15] mb-8 tracking-tight text-gradient">
          {title}
        </h1>

        {/* ─── Content ─── */}
        <article className="glass-card p-7 text-[#a8e6a8] text-sm leading-relaxed animate-fade-in-up">
          {children}
        </article>

        {/* ─── Footer ─── */}
        <footer className="mt-16 text-xs text-[#8bb88b] text-center">
          <Link href="/" className="text-[#8bb88b] no-underline hover:text-[var(--color-primary)] transition-colors">
            &lsaquo; На главную
          </Link>
        </footer>
      </div>
    </main>
  );
}
