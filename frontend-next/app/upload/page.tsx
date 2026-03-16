"use client";

import { AuthGuard } from "@/components/auth-guard";
import { UploadContent } from "@/components/upload-content";

export default function UploadPage() {
  return (
    <AuthGuard>
      <UploadContent />
    </AuthGuard>
  );
}
