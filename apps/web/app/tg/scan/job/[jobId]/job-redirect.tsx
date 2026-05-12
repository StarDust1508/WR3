"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export function JobRedirect({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [message, setMessage] = useState("Preparing audit…");

  useEffect(() => {
    const es = new EventSource(`/api/v1/scan/${jobId}/events`);
    es.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data) as {
          stage: string;
          scan_id?: string;
          message?: string;
        };
        if (data.message) setMessage(data.message);
        if (data.scan_id) {
          es.close();
          router.replace(`/tg/scan/${data.scan_id}`);
        }
      } catch {
        /* keep stream */
      }
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, [jobId, router]);

  return (
    <div className="py-16 text-center">
      <p className="text-sm text-zinc-500">{message}</p>
    </div>
  );
}
