import { ScanDetailMini } from "./scan-detail-mini";

export const dynamic = "force-dynamic";

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ScanDetailMini scanId={id} />;
}
