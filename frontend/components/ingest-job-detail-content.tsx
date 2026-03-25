"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/app-shell";
import { ReportDetailModal } from "@/components/report-detail-modal";
import { apiClient } from "@/lib/api/client";
import type { IngestJobDetailResponse } from "@/lib/api/types";

export function IngestJobDetailContent({ jobId }: { jobId: string }) {
  const [selectedReport, setSelectedReport] = useState<{ id: string; kind: "aggregate" | "forensic" } | null>(null);
  const jobQuery = useQuery({
    queryKey: ["ingest-job", jobId],
    queryFn: () => apiClient.get<IngestJobDetailResponse>(`/api/v1/ingest-jobs/${jobId}`),
  });

  const job = jobQuery.data;
  const items = job?.items ?? [];

  return (
    <AppShell
      title={`Ingest job ${jobId}`}
      description="Review the state of this submission and the outcome for each item."
      actions={
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link className="button-secondary inline-link-button" href="/ingest-jobs">
            Back to jobs
          </Link>
          <Link className="button-secondary inline-link-button" href="/upload">
            Open upload
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
          <p className="stat-label">Accepted</p>
          <p className="stat-value">{job?.accepted_count ?? 0}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Rejected</p>
          <p className="stat-value">{job?.rejected_count ?? 0}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Items</p>
          <p className="stat-value">{items.length}</p>
        </article>
      </section>

      <section className="surface-card stack">
        <div>
          <h2 className="section-title">Job detail</h2>
          <p className="section-intro">Check timestamps, totals, and item-by-item results for this ingest run.</p>
        </div>
        {jobQuery.isLoading ? <p className="status-text">Loading job detail...</p> : null}
        {jobQuery.error ? (
          <p className="error-text">{jobQuery.error instanceof Error ? jobQuery.error.message : "Failed to load job"}</p>
        ) : null}
        {job ? (
          <>
            <div className="domain-meta">
              <span>Submitted {job.submitted_at ?? "n/a"}</span>
              <span>Started {job.started_at ?? "n/a"}</span>
              <span>Completed {job.completed_at ?? "n/a"}</span>
              <span>Duplicate {job.duplicate_count ?? 0}</span>
              <span>Invalid {job.invalid_count ?? 0}</span>
              <span>Retries {job.retry_count ?? 0}</span>
            </div>
            {job.last_error ? <p className="error-text">Last worker error: {job.last_error}</p> : null}
            {items.length ? (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Seq</th>
                      <th>Item</th>
                      <th>Report type</th>
                      <th>Domain</th>
                      <th>Status</th>
                      <th>Reason</th>
                      <th>Report detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item, index) => (
                      <tr key={item.item_id ?? `${jobId}-${index}`}>
                        <td>{item.sequence_no ?? index + 1}</td>
                        <td>{item.item_id ?? "n/a"}</td>
                        <td>{item.report_type_detected ?? "n/a"}</td>
                        <td>{item.domain_detected ?? "n/a"}</td>
                        <td>{item.status ?? "n/a"}</td>
                        <td>{item.status_reason ?? "n/a"}</td>
                        <td>
                          {item.normalized_report_id && item.normalized_report_kind ? (
                            <button
                              className="button-link"
                              onClick={() => setSelectedReport({ id: item.normalized_report_id!, kind: item.normalized_report_kind! })}
                              type="button"
                            >
                              View report
                            </button>
                          ) : (
                            "n/a"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="status-text">No job items returned yet.</p>
            )}
          </>
        ) : null}
      </section>
      {selectedReport ? (
        <ReportDetailModal
          kind={selectedReport.kind}
          onClose={() => setSelectedReport(null)}
          reportId={selectedReport.id}
        />
      ) : null}
    </AppShell>
  );
}
