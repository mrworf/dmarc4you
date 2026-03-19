"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/app-shell";
import { apiClient } from "@/lib/api/client";
import type { DomainMonitoringHistoryEntry, DomainMonitoringTimelineResponse } from "@/lib/api/types";

function formatMaybeDate(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : "Not yet";
}

function nodeClass(direction: string): string {
  if (direction === "degraded") {
    return "timeline-node timeline-node-degraded";
  }
  if (direction === "improved") {
    return "timeline-node timeline-node-improved";
  }
  return "timeline-node timeline-node-neutral";
}

function changeBadgeClass(direction: string): string {
  if (direction === "degraded") {
    return "timeline-change-badge timeline-change-degraded";
  }
  if (direction === "improved") {
    return "timeline-change-badge timeline-change-improved";
  }
  return "timeline-change-badge timeline-change-neutral";
}

function renderChange(entry: DomainMonitoringHistoryEntry) {
  return (
    <article className="timeline-entry" key={entry.id}>
      <div className={nodeClass(entry.overall_direction)} aria-hidden="true" />
      <div className="timeline-entry-card surface-card">
        <div className="section-heading">
          <div className="stack" style={{ gap: 8 }}>
            <strong>{entry.summary}</strong>
            <div className="domain-meta">
              <span>{new Date(entry.changed_at).toLocaleString()}</span>
              <span>{entry.overall_direction}</span>
            </div>
          </div>
        </div>
        <div className="stack">
          {entry.changes.map((change, index) => (
            <div className="timeline-change-panel" key={`${entry.id}-${index}`}>
              <div className="timeline-change-row">
                <span className={changeBadgeClass(String(change.direction || "neutral"))}>
                  {String(change.direction || "neutral")}
                </span>
                <strong>{String(change.label || change.record_type || "DNS change")}</strong>
              </div>
              <div className="timeline-before-after">
                <div>
                  <p className="timeline-before-after-label">Before</p>
                  <pre className="code-block">{String(change.before_raw || change.before_value || "Not set")}</pre>
                </div>
                <div>
                  <p className="timeline-before-after-label">After</p>
                  <pre className="code-block">{String(change.after_raw || change.after_value || "Not set")}</pre>
                </div>
              </div>
              <p className="section-intro">{String(change.reason || "DNS change detected.")}</p>
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}

export function DomainMonitoringTimelineContent({ domainId }: { domainId: string }) {
  const timelineQuery = useQuery({
    queryKey: ["domain-monitoring-timeline", domainId],
    queryFn: () => apiClient.get<DomainMonitoringTimelineResponse>(`/api/v1/domains/${domainId}/monitoring/timeline`),
  });

  const domain = timelineQuery.data?.domain;
  const history = timelineQuery.data?.history ?? [];

  return (
    <AppShell
      title={domain ? `${domain.name} timeline` : "DNS change timeline"}
      description="Scroll through saved DNS changes and see whether each change strengthened or weakened DMARC, SPF, or DKIM posture."
      actions={
        <div className="section-actions">
          <Link className="button-secondary" href={`/domains/${domainId}`}>
            Back to domain
          </Link>
          <button className="button-secondary" onClick={() => timelineQuery.refetch()} type="button">
            Refresh
          </button>
        </div>
      }
    >
      {timelineQuery.isLoading ? <p className="status-text">Loading DNS change timeline...</p> : null}
      {timelineQuery.error ? (
        <p className="error-text">{timelineQuery.error instanceof Error ? timelineQuery.error.message : "Failed to load timeline"}</p>
      ) : null}

      {timelineQuery.data ? (
        <>
          <section className="surface-card stack">
            <div className="section-heading">
              <div className="stack" style={{ gap: 8 }}>
                <h2 className="section-title">Freshness</h2>
                <p className="section-intro">This is the last successful DNS poll, even if nothing changed and no timeline entry was saved.</p>
              </div>
            </div>
            <div className="panel-grid">
              <article className="stat-card">
                <p className="stat-label">Last successful poll</p>
                <p className="stat-value" style={{ fontSize: "1rem" }}>{formatMaybeDate(timelineQuery.data.last_checked_at)}</p>
              </article>
              <article className="stat-card">
                <p className="stat-label">Saved changes</p>
                <p className="stat-value">{history.length}</p>
              </article>
            </div>
          </section>

          <section className="surface-card stack">
            <div className="section-heading">
              <div className="stack" style={{ gap: 8 }}>
                <h2 className="section-title">Timeline</h2>
                <p className="section-intro">Red means posture weakened, green means it improved, and blue marks neutral structural changes.</p>
              </div>
            </div>
            {!history.length ? <p className="status-text">No DNS value changes have been recorded for this domain yet.</p> : null}
            {history.length ? <div className="timeline-list">{history.map((entry) => renderChange(entry))}</div> : null}
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
