"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { AppShell } from "@/components/app-shell";
import { apiClient, ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/context";
import type {
  DomainMonitoringHistoryEntry,
  DomainMonitoringResponse,
  TriggerDomainMonitoringCheckResponse,
  UpdateDomainMonitoringBody,
} from "@/lib/api/types";

function selectorsToText(values: string[]): string {
  return values.join("\n");
}

function parseSelectors(value: string): string[] {
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function formatMaybeDate(value?: string | null): string {
  return value ? new Date(value).toLocaleString() : "Not yet";
}

function directionClass(direction: string): string {
  if (direction === "degraded") {
    return "timeline-node timeline-node-degraded";
  }
  if (direction === "improved") {
    return "timeline-node timeline-node-improved";
  }
  return "timeline-node timeline-node-neutral";
}

function renderPreviewEntry(entry: DomainMonitoringHistoryEntry) {
  return (
    <article className="timeline-entry" key={entry.id}>
      <div className={directionClass(entry.overall_direction)} aria-hidden="true" />
      <div className="timeline-entry-card">
        <div className="section-heading">
          <div className="stack" style={{ gap: 8 }}>
            <strong>{entry.summary}</strong>
            <div className="domain-meta">
              <span>{new Date(entry.changed_at).toLocaleString()}</span>
              <span>{entry.overall_direction}</span>
            </div>
          </div>
        </div>
        <div className="stack" style={{ gap: 10 }}>
          {entry.changes.slice(0, 3).map((change, index) => (
            <div className="timeline-change-row" key={`${entry.id}-${index}`}>
              <span className={`timeline-change-badge timeline-change-${String(change.direction || "neutral")}`}>
                {String(change.direction || "neutral")}
              </span>
              <span>{String(change.reason || change.label || "DNS change")}</span>
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}

export function DomainMonitoringDetailContent({ domainId }: { domainId: string }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [enabled, setEnabled] = useState(false);
  const [selectorText, setSelectorText] = useState("");

  const monitoringQuery = useQuery({
    queryKey: ["domain-monitoring", domainId],
    queryFn: () => apiClient.get<DomainMonitoringResponse>(`/api/v1/domains/${domainId}/monitoring`),
  });

  const domain = monitoringQuery.data?.domain;
  const canManage = user?.role === "super-admin" || user?.role === "admin";

  useEffect(() => {
    if (!monitoringQuery.data) {
      return;
    }
    setEnabled(Boolean(monitoringQuery.data.domain.monitoring_enabled));
    setSelectorText(selectorsToText(monitoringQuery.data.dkim_selectors));
  }, [monitoringQuery.data]);

  const updateMutation = useMutation({
    mutationFn: (body: UpdateDomainMonitoringBody) =>
      apiClient.put<DomainMonitoringResponse>(`/api/v1/domains/${domainId}/monitoring`, body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["domain-monitoring", domainId] });
      await queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
  });

  const triggerMutation = useMutation({
    mutationFn: () =>
      apiClient.post<TriggerDomainMonitoringCheckResponse>(`/api/v1/domains/${domainId}/monitoring/check`),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["domain-monitoring", domainId] });
      await queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
  });

  async function handleSave() {
    await updateMutation.mutateAsync({
      enabled,
      dkim_selectors: parseSelectors(selectorText),
    });
  }

  const currentState = monitoringQuery.data?.current_state;
  const saveError = updateMutation.error instanceof ApiError ? updateMutation.error.message : null;
  const triggerError = triggerMutation.error instanceof ApiError ? triggerMutation.error.message : null;

  return (
    <AppShell
      title={domain ? domain.name : "Domain monitoring"}
      description="Review live DMARC, SPF, and DKIM DNS posture for this domain."
      actions={
        <div className="section-actions">
          <Link className="button-secondary" href="/domains">
            Back to domains
          </Link>
          <button className="button-secondary" onClick={() => monitoringQuery.refetch()} type="button">
            Refresh
          </button>
        </div>
      }
    >
      {monitoringQuery.isLoading ? <p className="status-text">Loading domain monitoring...</p> : null}
      {monitoringQuery.error ? (
        <p className="error-text">
          {monitoringQuery.error instanceof Error ? monitoringQuery.error.message : "Failed to load domain monitoring"}
        </p>
      ) : null}

      {domain ? (
        <>
          <section className="panel-grid">
            <article className="stat-card">
              <p className="stat-label">Monitoring</p>
              <p className="stat-value">{domain.monitoring_enabled ? "Enabled" : "Disabled"}</p>
            </article>
            <article className="stat-card">
              <p className="stat-label">Last successful check</p>
              <p className="stat-value" style={{ fontSize: "1rem" }}>{formatMaybeDate(domain.monitoring_last_checked_at)}</p>
            </article>
            <article className="stat-card">
              <p className="stat-label">Next check</p>
              <p className="stat-value" style={{ fontSize: "1rem" }}>{formatMaybeDate(domain.monitoring_next_check_at)}</p>
            </article>
          </section>

          {domain.monitoring_failure_active ? (
            <section className="surface-card stack">
              <div className="section-heading">
                <div className="stack" style={{ gap: 8 }}>
                  <h2 className="section-title">Current lookup failure</h2>
                  <p className="section-intro">
                    DNS lookup failures are backend-logged and do not replace the last successful poll timestamp.
                  </p>
                </div>
              </div>
              <p className="error-text">{domain.monitoring_last_failure_summary || "DNS lookup failed."}</p>
              <p className="section-intro">First failure in the current streak: {formatMaybeDate(domain.monitoring_last_failure_at)}</p>
            </section>
          ) : null}

          {canManage ? (
            <section className="surface-card stack">
              <div className="section-heading">
                <div className="stack" style={{ gap: 8 }}>
                  <h2 className="section-title">Monitoring settings</h2>
                  <p className="section-intro">Turn monitoring on for this domain and list the DKIM selectors you want checked.</p>
                </div>
                <div className="section-actions">
                  <button
                    className="button-secondary"
                    disabled={triggerMutation.isPending}
                    onClick={() => triggerMutation.mutate()}
                    type="button"
                  >
                    Check now
                  </button>
                  <button className="button-primary" disabled={updateMutation.isPending} onClick={handleSave} type="button">
                    Save settings
                  </button>
                </div>
              </div>
              {saveError ? <p className="error-text">{saveError}</p> : null}
              {triggerError ? <p className="error-text">{triggerError}</p> : null}
              {triggerMutation.data?.state === "suppressed_recently" ? (
                <p className="status-text">A check was already triggered recently, so no new job was enqueued.</p>
              ) : null}
              <label className="field-label">
                <input checked={enabled} onChange={(event) => setEnabled(event.target.checked)} type="checkbox" />
                <span> Enable DNS monitoring for this domain</span>
              </label>
              <label className="field-label" htmlFor="dkim-selectors">
                DKIM selectors
              </label>
              <textarea
                className="textarea-input"
                id="dkim-selectors"
                onChange={(event) => setSelectorText(event.target.value)}
                placeholder={"selector1\nselector2"}
                rows={5}
                value={selectorText}
              />
              <p className="section-intro">Enter one selector per line. These are checked at `selector._domainkey.{domain?.name}`.</p>
            </section>
          ) : null}

          <section className="surface-card stack">
            <div className="section-heading">
              <div className="stack" style={{ gap: 8 }}>
                <h2 className="section-title">Current DNS state</h2>
                <p className="section-intro">Plain-language explanations are generated from the currently observed DNS records.</p>
              </div>
            </div>
            {!currentState ? <p className="status-text">No monitoring snapshot has been captured yet.</p> : null}
            {currentState ? (
              <div className="domain-list">
                {[currentState.dmarc, currentState.spf, ...currentState.dkim].map((record) => (
                  <article className="domain-row" key={record.host}>
                    <div className="section-heading">
                      <div className="stack" style={{ gap: 8 }}>
                        <strong>{record.host}</strong>
                        <div className="domain-meta">
                          <span>Status: {record.status}</span>
                          {record.ttl_seconds ? <span>TTL {record.ttl_seconds}s</span> : null}
                        </div>
                        <p>{record.summary || "No summary available."}</p>
                        <p className="section-intro">{record.explanation || "No explanation available."}</p>
                        <pre className="code-block">{record.raw_value || "No record found."}</pre>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : null}
          </section>

          <section className="surface-card stack">
            <div className="section-heading">
              <div className="stack" style={{ gap: 8 }}>
                <h2 className="section-title">Change history</h2>
                <p className="section-intro">Only actual DNS value changes are saved here. Poll freshness is shown separately above.</p>
              </div>
              <div className="section-actions">
                <Link className="button-secondary" href={`/domains/${domainId}/monitoring/timeline`}>
                  View timeline
                </Link>
              </div>
            </div>
            {!monitoringQuery.data?.history.length ? <p className="status-text">No monitoring changes recorded yet.</p> : null}
            {monitoringQuery.data?.history.length ? (
              <div className="timeline-list">
                {monitoringQuery.data.history.map((entry) => renderPreviewEntry(entry))}
              </div>
            ) : null}
          </section>
        </>
      ) : null}
    </AppShell>
  );
}
