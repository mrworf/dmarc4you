"use client";

import { AuthGuard } from "@/components/auth-guard";
import { IngestJobsContent } from "@/components/ingest-jobs-content";

export default function IngestJobsPage() {
  return (
    <AuthGuard>
      <IngestJobsContent />
    </AuthGuard>
  );
}
