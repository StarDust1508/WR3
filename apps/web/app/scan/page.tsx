import { Suspense } from "react";
import { ScanRunner } from "./scan-runner";

export const dynamic = "force-dynamic";

export default async function ScanPage({
  searchParams,
}: {
  searchParams: Promise<{ address?: string; network?: string }>;
}) {
  const params = await searchParams;
  const address = params.address ?? "";
  const network = params.network ?? "base";

  if (!address) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <p className="text-[#8bb88b]">Адрес не указан.</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="mb-8 animate-fade-in-up">
        <h1 className="text-2xl font-bold text-[#d4ffd4]">Сканирование</h1>
        <p className="mt-1 font-mono text-sm text-[#8bb88b]">
          <span className="inline-block rounded-md border border-[var(--color-border)] bg-[var(--color-primary)]/5 px-2 py-0.5 text-[var(--color-primary)]">
            {network}
          </span>
          <span className="mx-2 text-[#547654]">/</span>
          <span className="text-[#d4ffd4]/80">{address}</span>
        </p>
      </header>
      <Suspense
        fallback={
          <div className="glass-card flex items-center gap-3 p-6">
            <svg className="h-5 w-5 animate-spin text-[var(--color-primary)]" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-sm text-[#8bb88b]">Запускаю пайплайн аудита...</span>
          </div>
        }
      >
        <ScanRunner address={address} network={network} />
      </Suspense>
    </main>
  );
}
