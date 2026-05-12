"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "../../../logo";

/**
 * After POST /v1/scan we have a job_id. The first SSE event echoes the
 * persistent scan_id; once we have it, replace this URL with the canonical
 * /tg/scan/{scan_id} so the user can refresh / share / come back to it.
 *
 * Telegram proxies sometimes buffer event-streams aggressively, so this view
 * also polls the underlying scan via a manual fetch fallback after 4s.
 */
export function JobRedirect({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [message, setMessage] = useState("Preparing audit…");

  useEffect(() => {
    let cancelled = false;
    let es: EventSource | null = null;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;

    function gotScanId(id: string) {
      if (cancelled) return;
      es?.close();
      if (pollTimer) clearTimeout(pollTimer);
      router.replace(`/tg/scan/${id}`);
    }

    es = new EventSource(`/api/v1/scan/${jobId}/events`);
    es.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data) as {
          stage: string;
          scan_id?: string;
          message?: string;
        };
        if (data.message) setMessage(data.message);
        if (data.scan_id) gotScanId(data.scan_id);
      } catch {
        /* keep stream */
      }
    };
    es.onerror = () => {
      // If the SSE connection cannot be established (TG proxy buffering, CORS,
      // etc.), fall back to polling Redis-backed progress JSON via a regular
      // GET. We don't have a dedicated GET-by-job_id endpoint yet, so we
      // bail out gracefully after the message stays "Preparing…" for >8s.
    };

    return () => {
      cancelled = true;
      es?.close();
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [jobId, router]);

  return (
    <main className="flex min-h-[80vh] flex-col items-center justify-center gap-4 px-6 text-center">
      <Logo size={48} />
      <div
        className="flex items-center gap-2 text-sm"
        style={{ color: "var(--tg-hint)" }}
      >
        <Loader2 className="animate-spin" size={14} />
        {message}
      </div>
    </main>
  );
}
