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
      <main className="min-h-screen bg-[#060a06] flex items-center justify-center px-6">
        <p className="text-lg text-[#6b8f6b]">Адрес не указан.</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#060a06] px-6 py-10 lg:py-14">
      <div className="mx-auto max-w-4xl">
        <header className="mb-10 animate-fade-in-up">
          <h1 className="text-3xl lg:text-4xl font-extrabold tracking-tight text-[#e2ffe2]">
            Сканирование
          </h1>
          <div className="mt-3 flex items-center gap-3 flex-wrap">
            <span className="inline-block rounded-lg border border-[#4ade80]/30 bg-[#4ade80]/10 px-3 py-1 font-mono text-sm font-semibold uppercase text-[#4ade80]">
              {network}
            </span>
            <span className="text-[#3d5c3d]">/</span>
            <span className="font-mono text-base text-[#a8e6a8] break-all">{address}</span>
          </div>
        </header>
        <Suspense
          fallback={
            <div className="rounded-2xl border border-[#1a2e1a]/60 bg-[#0c120c] flex items-center gap-4 p-8">
              <svg className="h-6 w-6 animate-spin text-[#4ade80]" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-base text-[#8bb88b]">Запускаю пайплайн аудита...</span>
            </div>
          }
        >
          <ScanRunner address={address} network={network} />
        </Suspense>
      </div>
    </main>
  );
}
