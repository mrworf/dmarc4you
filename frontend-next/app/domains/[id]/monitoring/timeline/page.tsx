import { AuthGuard } from "@/components/auth-guard";
import { DomainMonitoringTimelineContent } from "@/components/domain-monitoring-timeline-content";

export default async function DomainMonitoringTimelinePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <AuthGuard>
      <DomainMonitoringTimelineContent domainId={id} />
    </AuthGuard>
  );
}
