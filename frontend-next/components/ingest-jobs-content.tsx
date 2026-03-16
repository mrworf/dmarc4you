"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/app-shell";
import { apiClient } from "@/lib/api/client";
import type { IngestJobsResponse } from "@/lib/api/types";

export function IngestJobsContent() {
  const jobsQuery = useQuery({
    queryKey: ["ingest-jobs"],
    queryFn: () => apiClient.get<IngestJobsResponse>("/api/v1/ingest-jobs"),
  });

  const jobs = jobsQuery.data?.jobs ?? [];

  return (
    <AppShell
      title="Ingest Jobs"
      description="Track recent submissions and open a job to review its outcome."
      actions={
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link className="button-secondary inline-link-button" href="/upload">
            Open upload
          </Link>
          <button className="button-secondary" onClick={() => jobsQuery.refetch()} type="button">
            Refresh
          </button>
        </div>
      }
    >
      <section className="panel-grid">
        <article className="stat-card">
          <p className="stat-label">Recent jobs</p>
          <p className="stat-value">{jobs.length}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Queued</p>
          <p className="stat-value">{jobs.filter((job) => job.state === "queued").length}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Running</p>
          <p className="stat-value">{jobs.filter((job) => job.state === "running").length}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Completed</p>
          <p className="stat-value">{jobs.filter((job) => job.state.startsWith("completed")).length}</p>
        </article>
      </section>

      <section className="surface-card stack">
        <div>
          <h2 className="section-title">Recent jobs</h2>
          <p className="section-intro">Open a job to see report status, outcomes, and any errors.</p>
        </div>

        {jobsQuery.isLoading ? <p className="status-text">Loading ingest jobs...</p> : null}
        {jobsQuery.error ? (
          <p className="error-text">{jobsQuery.error instanceof Error ? jobsQuery.error.message : "Failed to load ingest jobs"}</p>
        ) : null}

        {!jobsQuery.isLoading && !jobsQuery.error && !jobs.length ? (
          <p className="status-text">No ingest jobs are visible for this account yet.</p>
        ) : null}

        {jobs.length ? (
          <div className="domain-list">
            {jobs.map((job) => (
              <article className="domain-row" key={job.job_id}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                  <Link className="inline-link monospace" href={`/ingest-jobs/${job.job_id}`}>
                    {job.job_id}
                  </Link>
                  <span className="pill">{job.state}</span>
                </div>
                <div className="domain-meta">
                  <span>Submitted {job.submitted_at ? new Date(job.submitted_at).toLocaleString() : "n/a"}</span>
                  <Link className="inline-link" href={`/ingest-jobs/${job.job_id}`}>
                    View detail
                  </Link>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}
