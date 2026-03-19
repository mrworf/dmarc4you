import { AuthGuard } from "@/components/auth-guard";
import { DomainMonitoringDetailContent } from "@/components/domain-monitoring-detail-content";

export default async function DomainDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <AuthGuard>
      <DomainMonitoringDetailContent domainId={id} />
    </AuthGuard>
  );
}
