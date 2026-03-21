"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { AppShell } from "@/components/app-shell";
import { apiClient, ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/context";
import type {
  DomainMonitoringDetailItem,
  DomainMonitoringHistoryEntry,
  DomainMonitoringRecordState,
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

function statusBadgeClass(status: string): string {
  if (status === "ok") {
    return "monitoring-status-badge monitoring-status-ok";
  }
  if (status === "missing") {
    return "monitoring-status-badge monitoring-status-missing";
  }
  return "monitoring-status-badge monitoring-status-error";
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

function renderDetailItem(item: DomainMonitoringDetailItem, recordHost: string) {
  const values = item.values?.length ? item.values : ["Not available"];
  const displayAsList = item.display === "list";

  return (
    <div className="monitoring-detail-row" key={`${recordHost}-${item.label}`}>
      <dt className="monitoring-detail-label">{item.label}</dt>
      <dd className="monitoring-detail-values">
        {displayAsList ? (
          <ul className="monitoring-detail-bullets">
            {values.map((value) => (
              <li key={`${recordHost}-${item.label}-${value}`}>
                {item.value_type === "email" && value.includes("@") ? (
                  <a className="inline-link" href={`mailto:${value}`}>
                    {value}
                  </a>
                ) : (
                  value
                )}
              </li>
            ))}
          </ul>
        ) : (
          values.map((value, index) => (
            <span key={`${recordHost}-${item.label}-${value}-${index}`}>
              {item.value_type === "email" && value.includes("@") ? (
                <a className="inline-link" href={`mailto:${value}`}>
                  {value}
                </a>
              ) : (
                value
              )}
            </span>
          ))
        )}
      </dd>
    </div>
  );
}

function renderRecordCard({
  title,
  subtitle,
  record,
}: {
  title: string;
  subtitle: string;
  record: DomainMonitoringRecordState;
}) {
  return (
    <article className="monitoring-record-card" key={record.host}>
      <div className="monitoring-record-header">
        <div className="stack" style={{ gap: 6 }}>
          <div className="section-heading" style={{ gap: 12 }}>
            <h3 className="monitoring-record-title">{title}</h3>
            <span className={statusBadgeClass(record.status)}>{record.status}</span>
          </div>
          <p className="monitoring-record-subtitle">{subtitle}</p>
          <div className="domain-meta">
            <span>{record.host}</span>
            {record.ttl_seconds ? <span>TTL {record.ttl_seconds}s</span> : null}
          </div>
        </div>
      </div>
      {record.summary ? <p className="monitoring-record-summary">{record.summary}</p> : null}
      <dl className="monitoring-detail-list">
        {(record.details ?? []).map((item) => renderDetailItem(item, record.host))}
      </dl>
      {record.explanation ? <p className="monitoring-record-note">{record.explanation}</p> : null}
      <details className="monitoring-raw-disclosure">
        <summary>Show raw record</summary>
        <pre className="code-block">{record.raw_value || "No record found."}</pre>
      </details>
    </article>
  );
}

function renderEmptyDkimCard(domainName: string) {
  return (
    <article className="monitoring-record-card monitoring-record-card-empty">
      <div className="stack" style={{ gap: 8 }}>
        <h3 className="monitoring-record-title">DKIM</h3>
        <p className="monitoring-record-subtitle">No DKIM selectors are configured for monitoring yet.</p>
        <p className="monitoring-record-note">
          Add one or more selectors in Edit settings to check DNS keys such as
          {" "}
          <span className="monospace">selector._domainkey.{domainName}</span>.
        </p>
      </div>
    </article>
  );
}

export function DomainMonitoringDetailContent({ domainId }: { domainId: string }) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [draftEnabled, setDraftEnabled] = useState(false);
  const [draftSelectorText, setDraftSelectorText] = useState("");

  const monitoringQuery = useQuery({
    queryKey: ["domain-monitoring", domainId],
    queryFn: () => apiClient.get<DomainMonitoringResponse>(`/api/v1/domains/${domainId}/monitoring`),
  });

  const domain = monitoringQuery.data?.domain;
  const canManage = user?.role === "super-admin" || user?.role === "admin";

  useEffect(() => {
    if (!monitoringQuery.data || !isEditOpen) {
      return;
    }
    setDraftEnabled(Boolean(monitoringQuery.data.domain.monitoring_enabled));
    setDraftSelectorText(selectorsToText(monitoringQuery.data.dkim_selectors));
  }, [isEditOpen, monitoringQuery.data]);

  useEffect(() => {
    if (!isEditOpen) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsEditOpen(false);
      }
    }

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isEditOpen]);

  const updateMutation = useMutation({
    mutationFn: (body: UpdateDomainMonitoringBody) =>
      apiClient.put<DomainMonitoringResponse>(`/api/v1/domains/${domainId}/monitoring`, body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["domain-monitoring", domainId] });
      await queryClient.invalidateQueries({ queryKey: ["domains"] });
      setIsEditOpen(false);
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
      enabled: draftEnabled,
      dkim_selectors: parseSelectors(draftSelectorText),
    });
  }

  function openEditModal() {
    if (!monitoringQuery.data) {
      return;
    }
    setDraftEnabled(Boolean(monitoringQuery.data.domain.monitoring_enabled));
    setDraftSelectorText(selectorsToText(monitoringQuery.data.dkim_selectors));
    setIsEditOpen(true);
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
          {canManage ? (
            <button className="button-primary" onClick={openEditModal} type="button">
              Edit
            </button>
          ) : null}
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
              <p className="stat-value" style={{ fontSize: "1rem" }}>
                {formatMaybeDate(domain.monitoring_last_checked_at)}
              </p>
            </article>
            <article className="stat-card">
              <p className="stat-label">Next check</p>
              <p className="stat-value" style={{ fontSize: "1rem" }}>
                {formatMaybeDate(domain.monitoring_next_check_at)}
              </p>
            </article>
          </section>

          {domain.monitoring_failure_active ? (
            <section className="surface-card stack">
              <div className="section-heading">
                <div className="stack" style={{ gap: 8 }}>
                  <h2 className="section-title">Current lookup failure</h2>
                  <p className="section-intro">
                    The last successful snapshot is still shown below while the current DNS lookup issue is investigated.
                  </p>
                </div>
              </div>
              <p className="error-text">{domain.monitoring_last_failure_summary || "DNS lookup failed."}</p>
              <p className="section-intro">First failure in the current streak: {formatMaybeDate(domain.monitoring_last_failure_at)}</p>
            </section>
          ) : null}

          <section className="surface-card stack">
            <div className="section-heading">
              <div className="stack" style={{ gap: 8 }}>
                <h2 className="section-title">Current DNS state</h2>
                <p className="section-intro">Each card summarizes the most recently observed DNS record in plain language.</p>
              </div>
              {canManage ? (
                <div className="section-actions">
                  <button
                    className="button-secondary"
                    disabled={triggerMutation.isPending}
                    onClick={() => triggerMutation.mutate()}
                    type="button"
                  >
                    Check now
                  </button>
                </div>
              ) : null}
            </div>
            {triggerError ? <p className="error-text">{triggerError}</p> : null}
            {triggerMutation.data?.state === "suppressed_recently" ? (
              <p className="status-text">A check was already triggered recently, so no new job was enqueued.</p>
            ) : null}
            {!currentState ? <p className="status-text">No monitoring snapshot has been captured yet.</p> : null}
            {currentState ? (
              <>
                <div className="domain-meta">
                  <span>Snapshot captured {new Date(currentState.checked_at).toLocaleString()}</span>
                  {currentState.ttl_seconds ? <span>Overall TTL {currentState.ttl_seconds}s</span> : null}
                </div>
                <div className="monitoring-card-grid">
                  {renderRecordCard({
                    title: "DMARC",
                    subtitle: "How receiving systems should handle unauthenticated mail for this domain.",
                    record: currentState.dmarc,
                  })}
                  {renderRecordCard({
                    title: "SPF",
                    subtitle: `Which addresses and services are allowed to send email as ${domain.name}.`,
                    record: currentState.spf,
                  })}
                  {currentState.dkim.length
                    ? currentState.dkim.map((record) =>
                        renderRecordCard({
                          title: "DKIM",
                          subtitle: "Published signing key status for a monitored selector.",
                          record,
                        }),
                      )
                    : renderEmptyDkimCard(domain.name)}
                </div>
              </>
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

      {isEditOpen && canManage && domain ? (
        <div className="modal-backdrop" onClick={() => setIsEditOpen(false)} role="presentation">
          <div
            aria-modal="true"
            className="modal-card surface-card dialog-card"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
          >
            <div className="modal-header">
              <div className="stack" style={{ gap: 8 }}>
                <p className="eyebrow">Monitoring</p>
                <h2 style={{ margin: 0 }}>Edit monitoring settings</h2>
                <p className="status-text" style={{ margin: 0 }}>
                  Enable monitoring and choose which DKIM selectors should be checked for {domain.name}.
                </p>
              </div>
              <button aria-label="Close monitoring settings" className="icon-button" onClick={() => setIsEditOpen(false)} type="button">
                ×
              </button>
            </div>
            <div className="stack" style={{ gap: 18 }}>
              {saveError ? <p className="error-text">{saveError}</p> : null}
              <div className="monitoring-toggle-group" role="group" aria-label="Monitoring status">
                <button
                  aria-pressed={draftEnabled}
                  className={`monitoring-toggle-button${draftEnabled ? " monitoring-toggle-button-active" : ""}`}
                  onClick={() => setDraftEnabled(true)}
                  type="button"
                >
                  Monitoring enabled
                </button>
                <button
                  aria-pressed={!draftEnabled}
                  className={`monitoring-toggle-button${!draftEnabled ? " monitoring-toggle-button-active" : ""}`}
                  onClick={() => setDraftEnabled(false)}
                  type="button"
                >
                  Monitoring disabled
                </button>
              </div>
              <label className="field-label" htmlFor="dkim-selectors">
                DKIM selectors
              </label>
              <textarea
                className="textarea-input"
                id="dkim-selectors"
                onChange={(event) => setDraftSelectorText(event.target.value)}
                rows={6}
                value={draftSelectorText}
              />
              <p className="section-intro">
                Enter one selector per line. These will be checked at
                {" "}
                <span className="monospace">selector._domainkey.{domain.name}</span>.
              </p>
              <p className="detail-card-subtle" style={{ margin: 0 }}>
                Example selectors: <span className="monospace">google</span>, <span className="monospace">default</span>,
                {" "}
                <span className="monospace">mail</span>.
              </p>
              <div className="dialog-actions">
                <button className="button-secondary" onClick={() => setIsEditOpen(false)} type="button">
                  Cancel
                </button>
                <button className="button-primary" disabled={updateMutation.isPending} onClick={handleSave} type="button">
                  Save settings
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
