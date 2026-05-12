import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "wr3 — AI-аудит смарт-контрактов",
  description:
    "Аудит смарт-контракта за 90 секунд. AI-движок для vibe-кодеров на BSC, Base, Arbitrum, Ethereum, Solana.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  openGraph: {
    title: "wr3 — AI-аудит смарт-контрактов",
    description: "Аудит смарт-контракта за 90 секунд. Для vibe-кодеров.",
    type: "website",
    locale: "ru_RU",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // `suppressHydrationWarning` is required on <html> and <body> because the
    // Telegram WebApp SDK (loaded with strategy="beforeInteractive" in
    // app/tg/layout.tsx) sets inline `--tg-theme-*` CSS variables on these
    // elements before React hydrates. The server-rendered markup has no such
    // attributes, so React would flag the difference as a hydration error.
    // The warning suppression is scoped to ONLY html+body — every other
    // element is still strictly checked.
    <html lang="ru" suppressHydrationWarning>
      <body
        className="min-h-screen bg-white text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50"
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
