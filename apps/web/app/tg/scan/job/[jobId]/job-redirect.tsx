"use client";

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
  const [message, setMessage] = useState("Готовлю аудит…");

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
      // bail out gracefully after the message stays "Preparing..." for >8s.
    };

    return () => {
      cancelled = true;
      es?.close();
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [jobId, router]);

  return (
    <main className="flex min-h-[80vh] flex-col items-center justify-center gap-6 px-6 text-center">
      <div className="tg-animate-in" style={{ animation: "tg-fade-in-up 0.5s ease-out both" }}>
        <div
          className="tg-logo-pulse"
          style={{
            display: "inline-flex",
            padding: 4,
            borderRadius: 10,
          }}
        >
          <Logo size={48} />
        </div>
      </div>

      <div className="tg-animate-in tg-delay-2 tg-animated-border" style={{ minWidth: 260 }}>
        <div className="tg-animated-border-inner flex flex-col items-center gap-5">
          <div
            className="tg-progress-dots"
            aria-label="Loading"
          >
            <span />
            <span />
            <span />
          </div>

          <p
            className="tg-shimmer text-sm font-medium"
          >
            {message}
          </p>

          <p
            className="text-[10px]"
            style={{ color: "var(--hb-text-muted)" }}
          >
            Обычно занимает 20-60 секунд
          </p>
        </div>
      </div>
    </main>
  );
}
