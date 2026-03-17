import { AuthGuard } from "@/components/auth-guard";
import { DomainMaintenanceJobDetailContent } from "@/components/domain-maintenance-job-detail-content";

export default async function DomainMaintenanceJobDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <AuthGuard>
      <DomainMaintenanceJobDetailContent jobId={id} />
    </AuthGuard>
  );
}
