"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/app-shell";
import { apiClient } from "@/lib/api/client";
import type { DomainMaintenanceJobMutationResponse } from "@/lib/api/types";

export function DomainMaintenanceJobDetailContent({ jobId }: { jobId: string }) {
  const jobQuery = useQuery({
    queryKey: ["domain-maintenance-job", jobId],
    queryFn: () => apiClient.get<DomainMaintenanceJobMutationResponse>(`/api/v1/domain-maintenance-jobs/${jobId}`),
  });

  const job = jobQuery.data?.job;

  return (
    <AppShell
      title={`Maintenance job ${jobId}`}
      description="Review the state and recompute counters for this domain maintenance run."
      actions={
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link className="button-secondary inline-link-button" href="/domains">
            Back to domains
          </Link>
          <button className="button-secondary" onClick={() => jobQuery.refetch()} type="button">
            Refresh
          </button>
        </div>
      }
    >
      <section className="panel-grid">
        <article className="stat-card">
          <p className="stat-label">State</p>
          <p className="stat-value">{job?.state ?? "..."}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Reports scanned</p>
          <p className="stat-value">{job?.reports_scanned ?? 0}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Records updated</p>
          <p className="stat-value">{job?.records_updated ?? 0}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Reports skipped</p>
          <p className="stat-value">{job?.reports_skipped ?? 0}</p>
        </article>
      </section>

      <section className="surface-card stack">
        <div>
          <h2 className="section-title">Job detail</h2>
          <p className="section-intro">Use this to confirm when recomputation started, what it touched, and whether follow-up is needed.</p>
        </div>
        {jobQuery.isLoading ? <p className="status-text">Loading maintenance job detail...</p> : null}
        {jobQuery.error ? (
          <p className="error-text">
            {jobQuery.error instanceof Error ? jobQuery.error.message : "Failed to load maintenance job"}
          </p>
        ) : null}
        {job ? (
          <>
            <div className="domain-meta">
              <span>Domain {job.domain_name}</span>
              <span>Action {job.action}</span>
              <span>Submitted {job.submitted_at}</span>
              <span>Started {job.started_at ?? "n/a"}</span>
              <span>Completed {job.completed_at ?? "n/a"}</span>
            </div>
            {job.summary ? <p className="status-text">{job.summary}</p> : null}
            {job.last_error ? <p className="error-text">Last error: {job.last_error}</p> : null}
          </>
        ) : null}
      </section>
    </AppShell>
  );
}
