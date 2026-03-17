"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EditDashboardForm, type EditDashboardValues } from "@/components/edit-dashboard-form";
import { DashboardOwnershipPanel } from "@/components/dashboard-ownership-panel";
import { DashboardSharingPanel } from "@/components/dashboard-sharing-panel";
import { ReportDetailModal } from "@/components/report-detail-modal";
import { SlideOverPanel } from "@/components/slide-over-panel";
import { AggregateSearchResultsTable } from "@/components/search-results-table";
import { apiClient, ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/context";
import type {
  DashboardDetailResponse,
  DomainsResponse,
  DashboardValidateUpdateResponse,
  SearchRecordsBody,
  SearchRecordsResponse,
  UpdateDashboardBody,
} from "@/lib/api/types";
import { buildSearchParams, parseIntegerParam, parseStringParam } from "@/lib/url-state";

type DashboardFilterState = {
  from: string;
  to: string;
  groupBy: string;
  includeDmarcAlignment: string;
  includeDkimAlignment: string;
  includeSpfAlignment: string;
  includeSpf: string;
  includeDkim: string;
  includeDisposition: string;
  excludeDmarcAlignment: string;
  excludeDkimAlignment: string;
  excludeSpfAlignment: string;
  excludeSpf: string;
  excludeDkim: string;
  excludeDisposition: string;
  page: number;
};

const groupingOptions = [
  { value: "", label: "No grouping" },
  { value: "record_date", label: "Record date" },
  { value: "source_ip", label: "Source IP" },
  { value: "resolved_name", label: "Resolved hostname" },
  { value: "resolved_name_domain", label: "Resolved hostname domain" },
];

const resultOptions = [
  { value: "", label: "Any result" },
  { value: "pass", label: "Pass" },
  { value: "fail", label: "Fail" },
];

const dispositionOptions = [
  { value: "", label: "Any disposition" },
  { value: "none", label: "None" },
  { value: "quarantine", label: "Quarantine" },
  { value: "reject", label: "Reject" },
];

const dmarcAlignmentOptions = [
  { value: "", label: "Any alignment" },
  { value: "pass", label: "Pass" },
  { value: "fail", label: "Fail" },
  { value: "unknown", label: "Unknown" },
];

const alignmentModeOptions = [
  { value: "", label: "Any alignment" },
  { value: "strict", label: "Strict" },
  { value: "relaxed", label: "Relaxed" },
  { value: "none", label: "None" },
  { value: "unknown", label: "Unknown" },
];

function parseDashboardState(searchParams: URLSearchParams): DashboardFilterState {
  return {
    from: parseStringParam(searchParams.get("from")),
    to: parseStringParam(searchParams.get("to")),
    groupBy: parseStringParam(searchParams.get("group_by")),
    includeDmarcAlignment: parseStringParam(searchParams.get("include_dmarc_alignment")),
    includeDkimAlignment: parseStringParam(searchParams.get("include_dkim_alignment")),
    includeSpfAlignment: parseStringParam(searchParams.get("include_spf_alignment")),
    includeSpf: parseStringParam(searchParams.get("include_spf")),
    includeDkim: parseStringParam(searchParams.get("include_dkim")),
    includeDisposition: parseStringParam(searchParams.get("include_disposition")),
    excludeDmarcAlignment: parseStringParam(searchParams.get("exclude_dmarc_alignment")),
    excludeDkimAlignment: parseStringParam(searchParams.get("exclude_dkim_alignment")),
    excludeSpfAlignment: parseStringParam(searchParams.get("exclude_spf_alignment")),
    excludeSpf: parseStringParam(searchParams.get("exclude_spf")),
    excludeDkim: parseStringParam(searchParams.get("exclude_dkim")),
    excludeDisposition: parseStringParam(searchParams.get("exclude_disposition")),
    page: parseIntegerParam(searchParams.get("page"), 1),
  };
}

function buildDashboardParams(state: DashboardFilterState): string {
  return buildSearchParams({
    from: state.from,
    to: state.to,
    group_by: state.groupBy,
    include_dmarc_alignment: state.includeDmarcAlignment,
    include_dkim_alignment: state.includeDkimAlignment,
    include_spf_alignment: state.includeSpfAlignment,
    include_spf: state.includeSpf,
    include_dkim: state.includeDkim,
    include_disposition: state.includeDisposition,
    exclude_dmarc_alignment: state.excludeDmarcAlignment,
    exclude_dkim_alignment: state.excludeDkimAlignment,
    exclude_spf_alignment: state.excludeSpfAlignment,
    exclude_spf: state.excludeSpf,
    exclude_dkim: state.excludeDkim,
    exclude_disposition: state.excludeDisposition,
    page: state.page > 1 ? String(state.page) : "",
  });
}

function buildSearchBody(domainNames: string[], state: DashboardFilterState): SearchRecordsBody {
  const include: Record<string, string[]> = {};
  const exclude: Record<string, string[]> = {};

  if (state.includeDmarcAlignment) {
    include.dmarc_alignment = [state.includeDmarcAlignment];
  }
  if (state.includeDkimAlignment) {
    include.dkim_alignment = [state.includeDkimAlignment];
  }
  if (state.includeSpfAlignment) {
    include.spf_alignment = [state.includeSpfAlignment];
  }
  if (state.includeSpf) {
    include.spf_result = [state.includeSpf];
  }
  if (state.includeDkim) {
    include.dkim_result = [state.includeDkim];
  }
  if (state.includeDisposition) {
    include.disposition = [state.includeDisposition];
  }
  if (state.excludeSpf) {
    exclude.spf_result = [state.excludeSpf];
  }
  if (state.excludeDmarcAlignment) {
    exclude.dmarc_alignment = [state.excludeDmarcAlignment];
  }
  if (state.excludeDkimAlignment) {
    exclude.dkim_alignment = [state.excludeDkimAlignment];
  }
  if (state.excludeSpfAlignment) {
    exclude.spf_alignment = [state.excludeSpfAlignment];
  }
  if (state.excludeDkim) {
    exclude.dkim_result = [state.excludeDkim];
  }
  if (state.excludeDisposition) {
    exclude.disposition = [state.excludeDisposition];
  }

  return {
    domains: domainNames,
    from: state.from || undefined,
    to: state.to || undefined,
    group_by: state.groupBy || undefined,
    include: Object.keys(include).length ? include : undefined,
    exclude: Object.keys(exclude).length ? exclude : undefined,
    page: state.page,
    page_size: 10,
  };
}

export function DashboardDetailContent({ dashboardId }: { dashboardId: string }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const currentState = useMemo(() => parseDashboardState(searchParams), [searchParams]);
  const [draftState, setDraftState] = useState<DashboardFilterState>(currentState);
  const [selectedAggregateReportId, setSelectedAggregateReportId] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSharingOpen, setIsSharingOpen] = useState(false);
  const [isOwnershipOpen, setIsOwnershipOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isScopeConfirmOpen, setIsScopeConfirmOpen] = useState(false);
  const [validateMessage, setValidateMessage] = useState<DashboardValidateUpdateResponse | null>(null);
  const [pendingUpdateValues, setPendingUpdateValues] = useState<UpdateDashboardBody | null>(null);

  useEffect(() => {
    setDraftState(currentState);
  }, [currentState]);

  const dashboardQuery = useQuery({
    queryKey: ["dashboard", dashboardId],
    queryFn: () => apiClient.get<DashboardDetailResponse>(`/api/v1/dashboards/${dashboardId}`),
  });
  const domainsQuery = useQuery({
    queryKey: ["domains"],
    queryFn: () => apiClient.get<DomainsResponse>("/api/v1/domains"),
    enabled: isEditing,
  });

  const domainNames = dashboardQuery.data?.domain_names ?? [];
  const searchBody = useMemo(() => buildSearchBody(domainNames, currentState), [currentState, domainNames]);

  const searchQuery = useQuery({
    queryKey: ["dashboard-search", dashboardId, searchBody],
    queryFn: () => apiClient.post<SearchRecordsResponse>("/api/v1/search", searchBody),
    enabled: domainNames.length > 0,
  });

  const dashboard = dashboardQuery.data;
  const result = searchQuery.data;
  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.page_size)) : 1;
  const canManageDashboard =
    !!user &&
    !!dashboard &&
    user.role !== "viewer" &&
    (dashboard.owner_user_id === user.id || user.role === "admin" || user.role === "super-admin");
  const canManageShares =
    !!user &&
    !!dashboard &&
    user.role !== "viewer" &&
    (dashboard.owner_user_id === user.id ||
      user.role === "manager" ||
      user.role === "admin" ||
      user.role === "super-admin");
  const canTransferOwnership = !!user && !!dashboard && (user.role === "admin" || user.role === "super-admin");

  const updateDashboard = useMutation({
    mutationFn: (values: UpdateDashboardBody) =>
      apiClient.put<DashboardDetailResponse>(`/api/v1/dashboards/${dashboardId}`, values),
    onSuccess: async (updatedDashboard) => {
      queryClient.setQueryData(["dashboard", dashboardId], updatedDashboard);
      await queryClient.invalidateQueries({ queryKey: ["dashboards"] });
      setIsEditing(false);
    },
  });

  const deleteDashboard = useMutation({
    mutationFn: () => apiClient.delete(`/api/v1/dashboards/${dashboardId}`),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["dashboards"] });
      router.replace("/dashboards");
    },
  });
  const exportDashboard = useMutation({
    mutationFn: () => apiClient.getText(`/api/v1/dashboards/${dashboardId}/export`),
  });

  function updateUrl(state: DashboardFilterState) {
    const nextParams = buildDashboardParams(state);
    router.replace(nextParams ? `${pathname}?${nextParams}` : pathname);
  }

  function applyFilters() {
    updateUrl({ ...draftState, page: 1 });
  }

  function resetFilters() {
    const resetState: DashboardFilterState = {
      from: "",
      to: "",
      groupBy: "",
      includeDmarcAlignment: "",
      includeDkimAlignment: "",
      includeSpfAlignment: "",
      includeSpf: "",
      includeDkim: "",
      includeDisposition: "",
      excludeDmarcAlignment: "",
      excludeDkimAlignment: "",
      excludeSpfAlignment: "",
      excludeSpf: "",
      excludeDkim: "",
      excludeDisposition: "",
      page: 1,
    };
    setDraftState(resetState);
    updateUrl(resetState);
  }

  function goToPage(page: number) {
    updateUrl({ ...currentState, page });
  }

  async function handleUpdateDashboard(values: EditDashboardValues) {
    setValidateMessage(null);
    setPendingUpdateValues(null);
    if (dashboard && !sameDomainScope(values.domain_ids, dashboard.domain_ids)) {
      const validation = await apiClient.post<DashboardValidateUpdateResponse>(
        `/api/v1/dashboards/${dashboardId}/validate-update`,
        { domain_ids: values.domain_ids },
      );
      setValidateMessage(validation);
      if (!validation.valid) {
        setPendingUpdateValues(values);
        setIsScopeConfirmOpen(true);
        return;
      }
    }
    await updateDashboard.mutateAsync(values);
  }

  async function confirmScopeUpdate() {
    if (!pendingUpdateValues) {
      return;
    }
    setIsScopeConfirmOpen(false);
    await updateDashboard.mutateAsync(pendingUpdateValues);
    setPendingUpdateValues(null);
  }

  async function handleDeleteDashboard() {
    await deleteDashboard.mutateAsync();
  }

  async function handleExportDashboard() {
    try {
      const yamlText = await exportDashboard.mutateAsync();
      const slug = (dashboard?.name ?? "dashboard").replace(/[^a-zA-Z0-9-_]/g, "-").replace(/-+/g, "-");
      const blob = new Blob([yamlText], { type: "application/x-yaml" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${slug || "dashboard"}.yaml`;
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      // Handled by mutation state below.
    }
  }

  const mutationError = updateDashboard.error instanceof ApiError ? updateDashboard.error.message : null;
  const deleteError = deleteDashboard.error instanceof ApiError ? deleteDashboard.error.message : null;
  const exportError = exportDashboard.error instanceof ApiError ? exportDashboard.error.message : null;

  return (
    <AppShell
      title={dashboard?.name ?? "Dashboard detail"}
      description="Review live results, update dashboard settings, and manage access for this view."
      actions={
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link className="button-secondary inline-link-button" href="/dashboards">
            Back to dashboards
          </Link>
          {canManageDashboard ? (
            <button className="button-secondary" onClick={() => setIsEditing(true)} type="button">
              Edit dashboard
            </button>
          ) : null}
          {canManageShares ? (
            <button className="button-secondary" onClick={() => setIsSharingOpen(true)} type="button">
              Manage sharing
            </button>
          ) : null}
          {canTransferOwnership ? (
            <button className="button-secondary" onClick={() => setIsOwnershipOpen(true)} type="button">
              Transfer ownership
            </button>
          ) : null}
          {canManageDashboard ? (
            <button className="button-secondary danger-button" onClick={() => setIsDeleteOpen(true)} type="button">
              {deleteDashboard.isPending ? "Deleting..." : "Delete dashboard"}
            </button>
          ) : null}
          <button className="button-secondary" onClick={handleExportDashboard} type="button">
            {exportDashboard.isPending ? "Exporting..." : "Export YAML"}
          </button>
          <button
            className="button-secondary"
            onClick={() => {
              dashboardQuery.refetch();
              searchQuery.refetch();
            }}
            type="button"
          >
            Refresh
          </button>
        </div>
      }
    >
      <section className="panel-grid">
        <article className="stat-card">
          <p className="stat-label">Domains in scope</p>
          <p className="stat-value">{dashboard?.domain_ids.length ?? 0}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Results shown</p>
          <p className="stat-value">{result?.items.length ?? 0}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Total matches</p>
          <p className="stat-value">{result?.total ?? 0}</p>
        </article>
      </section>

      <section className="surface-card stack">
        <div className="stack" style={{ gap: 10 }}>
          <div>
            <h2 className="section-title">Overview</h2>
            <p className="section-intro">Track the scope, last update time, and saved description for this dashboard.</p>
          </div>
          {dashboardQuery.isLoading ? <p className="status-text">Loading dashboard metadata...</p> : null}
          {dashboardQuery.error ? (
            <p className="error-text">
              {dashboardQuery.error instanceof Error ? dashboardQuery.error.message : "Failed to load dashboard"}
            </p>
          ) : null}
          {dashboard ? (
            <>
              {dashboard.description ? <p className="status-text">{dashboard.description}</p> : null}
              <div className="domain-meta">
                <span>ID {dashboard.id}</span>
                <span>Owner {dashboard.owner_user_id}</span>
                <span>Updated {new Date(dashboard.updated_at).toLocaleString()}</span>
              </div>
              <div className="pill-row">
                {dashboard.domain_names?.map((name) => (
                  <span className="pill" key={name}>
                    {name}
                  </span>
                ))}
              </div>
              {exportError ? <p className="error-text">{exportError}</p> : null}
              {deleteError ? <p className="error-text">{deleteError}</p> : null}
            </>
          ) : null}
        </div>
      </section>

      {dashboard && isEditing ? (
        <SlideOverPanel
          description="Update the dashboard name, description, and domain scope."
          error={mutationError ? <p className="error-text">{mutationError}</p> : null}
          onClose={() => setIsEditing(false)}
          open={isEditing}
          title="Edit dashboard"
        >
          {domainsQuery.isLoading ? <p className="status-text">Loading editable domain scope...</p> : null}
          {domainsQuery.error ? (
            <p className="error-text">
              {domainsQuery.error instanceof Error ? domainsQuery.error.message : "Failed to load domains"}
            </p>
          ) : null}
          {validateMessage && !validateMessage.valid ? (
            <div className="warning-panel">
              <p className="stat-label">Scope preflight warning</p>
              <p className="status-text">
                Updating this scope would affect {validateMessage.impacted_users.length} shared user(s).
              </p>
              <div className="pill-row">
                {validateMessage.impacted_users.map((impactedUser) => (
                  <span className="pill warning-pill" key={impactedUser.user_id}>
                    {impactedUser.username} ({impactedUser.access_level})
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          <EditDashboardForm
            dashboard={dashboard}
            domains={domainsQuery.data?.domains ?? []}
            isSubmitting={updateDashboard.isPending}
            onCancel={() => setIsEditing(false)}
            onSubmit={handleUpdateDashboard}
          />
        </SlideOverPanel>
      ) : null}

      {dashboard && isSharingOpen ? (
        <SlideOverPanel
          description="Control who can view or manage this dashboard."
          onClose={() => setIsSharingOpen(false)}
          open={isSharingOpen}
          title="Manage sharing"
        >
          <DashboardSharingPanel
            canManageShares={canManageShares}
            dashboardId={dashboard.id}
            viewerOnly={user?.role === "viewer"}
          />
        </SlideOverPanel>
      ) : null}

      {dashboard && isOwnershipOpen ? (
        <SlideOverPanel
          description="Transfer this dashboard to another eligible owner."
          onClose={() => setIsOwnershipOpen(false)}
          open={isOwnershipOpen}
          title="Transfer ownership"
        >
          <DashboardOwnershipPanel canTransferOwnership={canTransferOwnership} dashboard={dashboard} />
        </SlideOverPanel>
      ) : null}

      <section className="surface-card stack">
        <div>
          <h2 className="section-title">Filters</h2>
          <p className="section-intro">Refine the saved dashboard view and keep the current state in the URL.</p>
        </div>
        <div className="search-state-grid">
          <label className="field-label">
            From
            <input
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, from: event.target.value }))}
              type="date"
              value={draftState.from}
            />
          </label>
          <label className="field-label">
            To
            <input
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, to: event.target.value }))}
              type="date"
              value={draftState.to}
            />
          </label>
          <label className="field-label">
            Group by
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, groupBy: event.target.value }))}
              value={draftState.groupBy}
            >
              {groupingOptions.map((option) => (
                <option key={option.value || "none"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Include DMARC alignment
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, includeDmarcAlignment: event.target.value }))}
              value={draftState.includeDmarcAlignment}
            >
              {dmarcAlignmentOptions.map((option) => (
                <option key={`include-dmarc-alignment-${option.value || "any"}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Include DKIM alignment
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, includeDkimAlignment: event.target.value }))}
              value={draftState.includeDkimAlignment}
            >
              {alignmentModeOptions.map((option) => (
                <option key={`include-dkim-alignment-${option.value || "any"}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Include SPF alignment
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, includeSpfAlignment: event.target.value }))}
              value={draftState.includeSpfAlignment}
            >
              {alignmentModeOptions.map((option) => (
                <option key={`include-spf-alignment-${option.value || "any"}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Include SPF
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, includeSpf: event.target.value }))}
              value={draftState.includeSpf}
            >
              {resultOptions.map((option) => (
                <option key={`include-spf-${option.value || "any"}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Include DKIM
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, includeDkim: event.target.value }))}
              value={draftState.includeDkim}
            >
              {resultOptions.map((option) => (
                <option key={`include-dkim-${option.value || "any"}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Include disposition
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, includeDisposition: event.target.value }))}
              value={draftState.includeDisposition}
            >
              {dispositionOptions.map((option) => (
                <option key={`include-disposition-${option.value || "any"}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Exclude DMARC alignment
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, excludeDmarcAlignment: event.target.value }))}
              value={draftState.excludeDmarcAlignment}
            >
              {dmarcAlignmentOptions.map((option) => (
                <option key={`exclude-dmarc-alignment-${option.value || "any"}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Exclude DKIM alignment
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, excludeDkimAlignment: event.target.value }))}
              value={draftState.excludeDkimAlignment}
            >
              {alignmentModeOptions.map((option) => (
                <option key={`exclude-dkim-alignment-${option.value || "any"}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Exclude SPF alignment
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, excludeSpfAlignment: event.target.value }))}
              value={draftState.excludeSpfAlignment}
            >
              {alignmentModeOptions.map((option) => (
                <option key={`exclude-spf-alignment-${option.value || "any"}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Exclude SPF
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, excludeSpf: event.target.value }))}
              value={draftState.excludeSpf}
            >
              {resultOptions.map((option) => (
                <option key={`exclude-spf-${option.value || "any"}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Exclude DKIM
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, excludeDkim: event.target.value }))}
              value={draftState.excludeDkim}
            >
              {resultOptions.map((option) => (
                <option key={`exclude-dkim-${option.value || "any"}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Exclude disposition
            <select
              className="field-input"
              onChange={(event) => setDraftState((current) => ({ ...current, excludeDisposition: event.target.value }))}
              value={draftState.excludeDisposition}
            >
              {dispositionOptions.map((option) => (
                <option key={`exclude-disposition-${option.value || "any"}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <button className="button-primary" onClick={applyFilters} type="button">
            Apply filters
          </button>
          <button className="button-secondary" onClick={resetFilters} type="button">
            Reset
          </button>
        </div>
      </section>

      <section className="surface-card stack">
        <div>
          <h2 className="section-title">Live results</h2>
          <p className="section-intro">Review the current aggregate records for the domains in this dashboard.</p>
        </div>
        {dashboard && !domainNames.length ? <p className="status-text">This dashboard has no domains in scope.</p> : null}
        {searchQuery.isLoading ? <p className="status-text">Loading live dashboard results...</p> : null}
        {searchQuery.error ? (
          <p className="error-text">
            {searchQuery.error instanceof Error ? searchQuery.error.message : "Failed to load dashboard results"}
          </p>
        ) : null}
        {result ? (
          <AggregateSearchResultsTable
            emptyMessage="No matching records yet for this dashboard scope."
            onViewReport={setSelectedAggregateReportId}
            result={result}
            visibleColumns={dashboard?.visible_columns}
          />
        ) : null}
        {result ? (
          <div className="pagination-row">
            <span className="status-text">
              Page {result.page} of {totalPages}
            </span>
            <div style={{ display: "flex", gap: 12 }}>
              <button
                className="button-secondary"
                disabled={currentState.page <= 1}
                onClick={() => goToPage(Math.max(1, currentState.page - 1))}
                type="button"
              >
                Previous
              </button>
              <button
                className="button-secondary"
                disabled={currentState.page >= totalPages}
                onClick={() => goToPage(currentState.page + 1)}
                type="button"
              >
                Next
              </button>
            </div>
          </div>
        ) : null}
      </section>
      {selectedAggregateReportId ? (
        <ReportDetailModal
          kind="aggregate"
          onClose={() => setSelectedAggregateReportId(null)}
          reportId={selectedAggregateReportId}
        />
      ) : null}
      <ConfirmDialog
        confirmLabel="Delete dashboard"
        confirmTone="danger"
        description="Delete this dashboard permanently? This cannot be undone."
        error={deleteError ? <p className="error-text">{deleteError}</p> : null}
        isPending={deleteDashboard.isPending}
        onCancel={() => setIsDeleteOpen(false)}
        onConfirm={() => {
          void handleDeleteDashboard();
        }}
        open={isDeleteOpen}
        title="Delete dashboard"
      />
      <ConfirmDialog
        confirmLabel="Continue update"
        description={
          validateMessage && !validateMessage.valid
            ? `This dashboard change would affect ${validateMessage.impacted_users.length} shared user(s). Continue anyway?`
            : ""
        }
        isPending={updateDashboard.isPending}
        onCancel={() => {
          setIsScopeConfirmOpen(false);
          setPendingUpdateValues(null);
        }}
        onConfirm={() => {
          void confirmScopeUpdate();
        }}
        open={isScopeConfirmOpen}
        title="Confirm scope change"
      />
    </AppShell>
  );
}

function sameDomainScope(nextDomainIds: string[], currentDomainIds: string[]): boolean {
  if (nextDomainIds.length !== currentDomainIds.length) {
    return false;
  }
  const nextSet = new Set(nextDomainIds);
  return currentDomainIds.every((domainId) => nextSet.has(domainId));
}
