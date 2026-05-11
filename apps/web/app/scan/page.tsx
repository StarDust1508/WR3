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
        <p className="text-zinc-600">No address provided.</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">Scanning</h1>
        <p className="mt-1 font-mono text-sm text-zinc-600 dark:text-zinc-400">
          {network} · {address}
        </p>
      </header>

      <Suspense fallback={<p>Initializing audit pipeline…</p>}>
        <ScanRunner address={address} network={network} />
      </Suspense>
    </main>
  );
}
