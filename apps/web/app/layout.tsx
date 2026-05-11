import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "wr3 — AI audit for smart contracts",
  description:
    "Audit your smart contract in 90 seconds. AI-powered. Built for vibe-coders on BSC, Base, Arbitrum, Ethereum, Solana.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  openGraph: {
    title: "wr3 — AI audit for smart contracts",
    description: "Audit your smart contract in 90 seconds. For vibe-coders.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50">
        {children}
      </body>
    </html>
  );
}
