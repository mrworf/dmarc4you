"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { AppShell } from "@/components/app-shell";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { SlideOverPanel } from "@/components/slide-over-panel";
import { apiClient, ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/context";
import type {
  ArchiveDomainBody,
  CreateDomainBody,
  DomainMutationResponse,
  DomainMaintenanceJobMutationResponse,
  DomainSummary,
  DomainsResponse,
  SetDomainRetentionBody,
} from "@/lib/api/types";

type DomainActionState =
  | { kind: "archive"; domain: DomainSummary }
  | { kind: "retention"; domain: DomainSummary }
  | null;

function formatJobAction(action: string) {
  if (action === "recompute_aggregate_reports") {
    return "Recompute aggregate reports";
  }
  return action;
}

export function DomainsContent() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [activeAction, setActiveAction] = useState<DomainActionState>(null);
  const [deleteDomain, setDeleteDomain] = useState<DomainSummary | null>(null);
  const [recomputeDomain, setRecomputeDomain] = useState<DomainSummary | null>(null);
  const [createName, setCreateName] = useState("");
  const [archiveRetentionDays, setArchiveRetentionDays] = useState("");
  const [retentionDays, setRetentionDays] = useState("");

  const domainsQuery = useQuery({
    queryKey: ["domains"],
    queryFn: () => apiClient.get<DomainsResponse>("/api/v1/domains"),
  });

  const createDomain = useMutation({
    mutationFn: (body: CreateDomainBody) => apiClient.post<DomainMutationResponse>("/api/v1/domains", body),
    onSuccess: async () => {
      setCreateName("");
      setIsCreateOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
  });

  const archiveDomain = useMutation({
    mutationFn: ({ domainId, body }: { domainId: string; body: ArchiveDomainBody }) =>
      apiClient.post<DomainMutationResponse>(`/api/v1/domains/${domainId}/archive`, body),
    onSuccess: async () => {
      setArchiveRetentionDays("");
      setActiveAction(null);
      await queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
  });

  const restoreDomain = useMutation({
    mutationFn: (domainId: string) => apiClient.post<DomainMutationResponse>(`/api/v1/domains/${domainId}/restore`),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
  });

  const setDomainRetention = useMutation({
    mutationFn: ({ domainId, body }: { domainId: string; body: SetDomainRetentionBody }) =>
      apiClient.post<DomainMutationResponse>(`/api/v1/domains/${domainId}/retention`, body),
    onSuccess: async () => {
      setRetentionDays("");
      setActiveAction(null);
      await queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
  });

  const pauseRetention = useMutation({
    mutationFn: (domainId: string) => apiClient.post<DomainMutationResponse>(`/api/v1/domains/${domainId}/retention/pause`, {}),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
  });

  const unpauseRetention = useMutation({
    mutationFn: (domainId: string) => apiClient.post<DomainMutationResponse>(`/api/v1/domains/${domainId}/retention/unpause`),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
  });

  const deleteDomainMutation = useMutation({
    mutationFn: (domainId: string) => apiClient.delete(`/api/v1/domains/${domainId}`),
    onSuccess: async () => {
      setDeleteDomain(null);
      await queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
  });

  const recomputeReports = useMutation({
    mutationFn: (domainId: string) =>
      apiClient.post<DomainMaintenanceJobMutationResponse>(`/api/v1/domains/${domainId}/recompute`),
    onSuccess: async () => {
      setRecomputeDomain(null);
      await queryClient.invalidateQueries({ queryKey: ["domains"] });
    },
  });

  const domains = domainsQuery.data?.domains ?? [];
  const canManageDomains = user?.role === "super-admin";
  const activeCount = domains.filter((domain) => domain.status === "active").length;
  const archivedCount = domains.filter((domain) => domain.status === "archived").length;
  const createError = createDomain.error instanceof ApiError ? createDomain.error.message : null;
  const archiveError = archiveDomain.error instanceof ApiError ? archiveDomain.error.message : null;
  const retentionError = setDomainRetention.error instanceof ApiError ? setDomainRetention.error.message : null;
  const restoreError = restoreDomain.error instanceof ApiError ? restoreDomain.error.message : null;
  const pauseError = pauseRetention.error instanceof ApiError ? pauseRetention.error.message : null;
  const unpauseError = unpauseRetention.error instanceof ApiError ? unpauseRetention.error.message : null;
  const deleteError = deleteDomainMutation.error instanceof ApiError ? deleteDomainMutation.error.message : null;
  const recomputeError = recomputeReports.error instanceof ApiError ? recomputeReports.error.message : null;
  const listMutationError = restoreError ?? pauseError ?? unpauseError;
  const canRecomputeReports = user?.role === "super-admin" || user?.role === "admin";

  async function handleCreateDomain() {
    if (!createName.trim()) {
      return;
    }
    await createDomain.mutateAsync({ name: createName.trim() });
  }

  async function handleArchiveDomain() {
    if (!activeAction || activeAction.kind !== "archive") {
      return;
    }
    const parsedDays = archiveRetentionDays.trim() ? Number.parseInt(archiveRetentionDays, 10) : undefined;
    await archiveDomain.mutateAsync({
      domainId: activeAction.domain.id,
      body: parsedDays ? { retention_days: parsedDays } : {},
    });
  }

  async function handleSetRetention() {
    if (!activeAction || activeAction.kind !== "retention") {
      return;
    }
    const parsedDays = Number.parseInt(retentionDays, 10);
    if (!parsedDays) {
      return;
    }
    await setDomainRetention.mutateAsync({
      domainId: activeAction.domain.id,
      body: { retention_days: parsedDays },
    });
  }

  return (
    <AppShell
      title="Domains"
      description="View your active domain scope and manage domain lifecycle actions."
      actions={
        <div className="section-actions">
          {canManageDomains ? (
            <button className="button-primary" onClick={() => setIsCreateOpen(true)} type="button">
              Create domain
            </button>
          ) : null}
          <button className="button-secondary" onClick={() => domainsQuery.refetch()} type="button">
            Refresh
          </button>
        </div>
      }
    >
      <section className="panel-grid">
        <article className="stat-card">
          <p className="stat-label">Visible domains</p>
          <p className="stat-value">{domains.length}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Active</p>
          <p className="stat-value">{activeCount}</p>
        </article>
        {canManageDomains ? (
          <article className="stat-card">
            <p className="stat-label">Archived</p>
            <p className="stat-value">{archivedCount}</p>
          </article>
        ) : null}
      </section>

      <section className="surface-card stack">
        <div className="section-heading">
          <div className="stack" style={{ gap: 8 }}>
            <h2 className="section-title">Domain inventory</h2>
            <p className="section-intro">
              Keep track of active coverage, archived domains, and retention status.
            </p>
          </div>
        </div>
        {listMutationError ? <p className="error-text">{listMutationError}</p> : null}
        {domainsQuery.isLoading ? <p className="status-text">Loading domains...</p> : null}
        {domainsQuery.error ? (
          <p className="error-text">{domainsQuery.error instanceof Error ? domainsQuery.error.message : "Failed to load domains"}</p>
        ) : null}
        {!domainsQuery.isLoading && !domainsQuery.error && !domains.length ? (
          <p className="status-text">No domains are visible for this account yet.</p>
        ) : null}
        {domains.length ? (
          <div className="domain-list">
            {domains.map((domain) => (
              <article className="domain-row" key={domain.id}>
                <div className="section-heading">
                  <div className="stack" style={{ gap: 8 }}>
                    <strong>{domain.name}</strong>
                    <div className="domain-meta">
                      <span>Created {new Date(domain.created_at).toLocaleString()}</span>
                      {domain.archived_at ? <span>Archived {new Date(domain.archived_at).toLocaleString()}</span> : null}
                      {domain.retention_delete_at ? (
                        <span>Retention until {new Date(domain.retention_delete_at).toLocaleDateString()}</span>
                      ) : null}
                      {domain.retention_paused ? <span>Retention paused</span> : null}
                    </div>
                    {domain.latest_maintenance_job ? (
                      <div className="domain-meta">
                        <span>Maintenance: {domain.latest_maintenance_job.state}</span>
                        <span>{formatJobAction(domain.latest_maintenance_job.action)}</span>
                        <span>Submitted {new Date(domain.latest_maintenance_job.submitted_at).toLocaleString()}</span>
                        {domain.latest_maintenance_job.completed_at ? (
                          <span>Completed {new Date(domain.latest_maintenance_job.completed_at).toLocaleString()}</span>
                        ) : null}
                        <span>{domain.latest_maintenance_job.records_updated} records updated</span>
                        <Link className="button-link" href={`/domain-maintenance-jobs/${domain.latest_maintenance_job.job_id}`}>
                          View maintenance job
                        </Link>
                      </div>
                    ) : null}
                  </div>
                  <div className="section-actions">
                    <span className="pill">{domain.status}</span>
                    {canRecomputeReports ? (
                      <button
                        className="button-secondary"
                        disabled={domain.latest_maintenance_job?.state === "queued" || domain.latest_maintenance_job?.state === "processing"}
                        onClick={() => setRecomputeDomain(domain)}
                        type="button"
                      >
                        {domain.latest_maintenance_job?.state === "queued" || domain.latest_maintenance_job?.state === "processing"
                          ? "Recompute queued"
                          : "Recompute reports"}
                      </button>
                    ) : null}
                    {canManageDomains ? (
                      <>
                        {domain.status === "active" ? (
                          <button
                            className="button-secondary"
                            onClick={() => {
                              setArchiveRetentionDays("");
                              setActiveAction({ kind: "archive", domain });
                            }}
                            type="button"
                          >
                            Archive
                          </button>
                        ) : null}
                        {domain.status === "archived" ? (
                          <>
                            <button className="button-secondary" onClick={() => restoreDomain.mutate(domain.id)} type="button">
                              Restore
                            </button>
                            <button
                              className="button-secondary"
                              onClick={() => {
                                setRetentionDays(domain.retention_days ? String(domain.retention_days) : "");
                                setActiveAction({ kind: "retention", domain });
                              }}
                              type="button"
                            >
                              {domain.retention_days ? "Update retention" : "Set retention"}
                            </button>
                            {domain.retention_delete_at && !domain.retention_paused ? (
                              <button className="button-secondary" onClick={() => pauseRetention.mutate(domain.id)} type="button">
                                Pause retention
                              </button>
                            ) : null}
                            {domain.retention_paused ? (
                              <button className="button-secondary" onClick={() => unpauseRetention.mutate(domain.id)} type="button">
                                Resume retention
                              </button>
                            ) : null}
                            <button
                              className="button-secondary danger-button"
                              onClick={() => setDeleteDomain(domain)}
                              type="button"
                            >
                              Delete
                            </button>
                          </>
                        ) : null}
                      </>
                    ) : null}
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <SlideOverPanel
        description="Add a domain to begin collecting and managing reports for it."
        error={createError ? <p className="error-text">{createError}</p> : null}
        onClose={() => setIsCreateOpen(false)}
        open={isCreateOpen}
        title="Create domain"
      >
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            void handleCreateDomain();
          }}
        >
          <label className="field-label">
            Domain name
            <input
              className="field-input"
              onChange={(event) => setCreateName(event.target.value)}
              placeholder="example.com"
              value={createName}
            />
          </label>
          <div className="dialog-actions">
            <button className="button-secondary" onClick={() => setIsCreateOpen(false)} type="button">
              Cancel
            </button>
            <button className="button-primary" disabled={createDomain.isPending || !createName.trim()} type="submit">
              {createDomain.isPending ? "Creating..." : "Create domain"}
            </button>
          </div>
        </form>
      </SlideOverPanel>

      <SlideOverPanel
        description={
          activeAction?.kind === "archive"
            ? `Archive ${activeAction.domain.name} now, and optionally start a retention window.`
            : activeAction?.kind === "retention"
              ? `Adjust the retention period for ${activeAction.domain.name}.`
              : ""
        }
        error={
          activeAction?.kind === "archive"
            ? archiveError
              ? <p className="error-text">{archiveError}</p>
              : null
            : retentionError
              ? <p className="error-text">{retentionError}</p>
              : null
        }
        onClose={() => setActiveAction(null)}
        open={Boolean(activeAction)}
        title={activeAction?.kind === "archive" ? "Archive domain" : "Retention settings"}
      >
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            if (activeAction?.kind === "archive") {
              void handleArchiveDomain();
              return;
            }
            void handleSetRetention();
          }}
        >
          {activeAction?.kind === "archive" ? (
            <label className="field-label">
              Retention days
              <input
                className="field-input"
                min="1"
                onChange={(event) => setArchiveRetentionDays(event.target.value)}
                placeholder="Optional"
                type="number"
                value={archiveRetentionDays}
              />
            </label>
          ) : null}
          {activeAction?.kind === "retention" ? (
            <label className="field-label">
              Retention days
              <input
                className="field-input"
                min="1"
                onChange={(event) => setRetentionDays(event.target.value)}
                placeholder="30"
                type="number"
                value={retentionDays}
              />
            </label>
          ) : null}
          <div className="dialog-actions">
            <button className="button-secondary" onClick={() => setActiveAction(null)} type="button">
              Cancel
            </button>
            <button className="button-primary" disabled={archiveDomain.isPending || setDomainRetention.isPending} type="submit">
              {activeAction?.kind === "archive"
                ? archiveDomain.isPending
                  ? "Archiving..."
                  : "Archive domain"
                : setDomainRetention.isPending
                  ? "Saving..."
                  : "Save retention"}
            </button>
          </div>
        </form>
      </SlideOverPanel>

      <ConfirmDialog
        confirmLabel="Recompute reports"
        description={
          recomputeDomain
            ? `Recompute derived aggregate report data for ${recomputeDomain.name}. This runs in the background and refreshes stored alignment fields without re-ingesting reports.`
            : ""
        }
        error={recomputeError ? <p className="error-text">{recomputeError}</p> : null}
        isPending={recomputeReports.isPending}
        onCancel={() => setRecomputeDomain(null)}
        onConfirm={() => {
          if (recomputeDomain) {
            void recomputeReports.mutateAsync(recomputeDomain.id);
          }
        }}
        open={Boolean(recomputeDomain)}
        title="Recompute aggregate reports"
      />

      <ConfirmDialog
        confirmLabel="Delete domain"
        confirmTone="danger"
        description={
          deleteDomain
            ? `Delete ${deleteDomain.name} permanently? This removes the archived domain and its related data.`
            : ""
        }
        error={deleteError ? <p className="error-text">{deleteError}</p> : null}
        isPending={deleteDomainMutation.isPending}
        onCancel={() => setDeleteDomain(null)}
        onConfirm={() => {
          if (deleteDomain) {
            deleteDomainMutation.mutate(deleteDomain.id);
          }
        }}
        open={Boolean(deleteDomain)}
        title="Delete archived domain"
      />
    </AppShell>
  );
}
