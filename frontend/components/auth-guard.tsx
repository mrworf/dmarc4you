"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth/context";
import type { UserRole } from "@/lib/api/types";

export function AuthGuard({
  allowedRoles,
  children,
}: {
  allowedRoles?: UserRole[];
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { passwordChangeRequired, status, user } = useAuth();

  useEffect(() => {
    if (status === "anonymous") {
      router.replace("/login");
      return;
    }
    if (status === "authenticated" && passwordChangeRequired) {
      router.replace("/change-password");
      return;
    }
    if (status === "authenticated" && allowedRoles && user && !allowedRoles.includes(user.role)) {
      router.replace("/domains");
    }
  }, [allowedRoles, passwordChangeRequired, router, status, user]);

  if (status === "loading") {
    return (
      <main className="app-frame">
        <section className="surface-card">
          <p className="status-text">Bootstrapping session...</p>
        </section>
      </main>
    );
  }

  if (status !== "authenticated") {
    return null;
  }

  if (passwordChangeRequired) {
    return null;
  }

  if (allowedRoles && (!user || !allowedRoles.includes(user.role))) {
    return null;
  }

  return <>{children}</>;
}
