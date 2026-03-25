import { AuthGuard } from "@/components/auth-guard";
import { DashboardDetailContent } from "@/components/dashboard-detail-content";

export default async function DashboardDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <AuthGuard>
      <DashboardDetailContent dashboardId={id} />
    </AuthGuard>
  );
}
