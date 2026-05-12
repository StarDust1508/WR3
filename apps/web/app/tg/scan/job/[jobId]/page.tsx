/**
 * After POST /v1/scan we get a `job_id`. The persisted scan UUID is echoed
 * in every SSE event. This page subscribes briefly, grabs the scan_id, and
 * redirects to /tg/scan/{scan_id}.
 */
import { JobRedirect } from "./job-redirect";

export const dynamic = "force-dynamic";

export default async function Page({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;
  return <JobRedirect jobId={jobId} />;
}
