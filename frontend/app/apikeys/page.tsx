"use client";

import { ApiKeysContent } from "@/components/apikeys-content";
import { AuthGuard } from "@/components/auth-guard";

export default function ApiKeysPage() {
  return (
    <AuthGuard allowedRoles={["super-admin", "admin"]}>
      <ApiKeysContent />
    </AuthGuard>
  );
}
