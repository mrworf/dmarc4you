import { AuthGuard } from "@/components/auth-guard";
import { DomainsContent } from "@/components/domains-content";

export default function DomainsPage() {
  return (
    <AuthGuard>
      <DomainsContent />
    </AuthGuard>
  );
}
