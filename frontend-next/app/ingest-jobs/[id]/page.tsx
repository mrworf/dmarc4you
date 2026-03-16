import { AuthGuard } from "@/components/auth-guard";
import { IngestJobDetailContent } from "@/components/ingest-job-detail-content";

export default async function IngestJobDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <AuthGuard>
      <IngestJobDetailContent jobId={id} />
    </AuthGuard>
  );
}
