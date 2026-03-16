"use client";

import { AuthGuard } from "@/components/auth-guard";
import { UsersContent } from "@/components/users-content";

export default function UsersPage() {
  return (
    <AuthGuard allowedRoles={["super-admin", "admin"]}>
      <UsersContent />
    </AuthGuard>
  );
}
