"use client";

import { AuditContent } from "@/components/audit-content";
import { AuthGuard } from "@/components/auth-guard";

export default function AuditPage() {
  return (
    <AuthGuard allowedRoles={["super-admin"]}>
      <AuditContent />
    </AuthGuard>
  );
}
