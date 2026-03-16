"use client";

import { AuthGuard } from "@/components/auth-guard";
import { SearchContent } from "@/components/search-content";

export default function SearchPage() {
  return (
    <AuthGuard>
      <SearchContent />
    </AuthGuard>
  );
}
