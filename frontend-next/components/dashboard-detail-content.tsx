"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EditDashboardForm, type EditDashboardValues } from "@/components/edit-dashboard-form";
import { DashboardOwnershipPanel } from "@/components/dashboard-ownership-panel";
import { DashboardSharingPanel } from "@/components/dashboard-sharing-panel";
import { ReportDetailModal } from "@/components/report-detail-modal";
import { SlideOverPanel } from "@/components/slide-over-panel";
import {
  AggregateSearchResultsTable,
  GroupedAggregateResultsTable,
  type SearchQuickFilterOption,
} from "@/components/search-results-table";
import { apiClient, ApiError } from "@/lib/api/client";
import {
  addUniqueValue,
  appendQueryValue,
  aggregateGroupingOptions,
  buildAggregateExplorerContextKey,
  buildAggregateExplorerParams,
  buildAggregateSearchBody,
  buildGroupedSearchBody,
  defaultAggregateExplorerState,
  formatOptionLabel,
  getAvailableAggregateGroupingOptions,
  getSelectedAggregateGroupingValue,
  parseQueryTerms,
  parseAggregateExplorerState,
  removeQueryTerm,
  removeValue,
  toggleValue,
  type AggregateExplorerState,
} from "@/lib/aggregate-explorer-state";
import { useAuth } from "@/lib/auth/context";
import { useAggregateExplorerState } from "@/lib/use-aggregate-explorer-state";
import type {
  DashboardDetailResponse,
  DomainsResponse,
  DashboardValidateUpdateResponse,
  GroupPathPart,
  GroupedSearchResponse,
  SearchRecordsResponse,
  UpdateDashboardBody,
} from "@/lib/api/types";
type AppliedFilterChip = {
  id: string;
  label: string;
  tone?: "default" | "exclude";
  onRemove: () => void;
};

const resultOptions = ["pass", "fail"];
const dispositionOptions = ["none", "quarantine", "reject"];
const dmarcAlignmentOptions = ["pass", "fail", "unknown"];
const alignmentModeOptions = ["strict", "relaxed", "none", "unknown"];

function parseDashboardState(searchParams: URLSearchParams): AggregateExplorerState {
  return parseAggregateExplorerState(searchParams, { includeDomains: false });
}

function appendFacetChips(
  chips: AppliedFilterChip[],
  label: string,
  keyPrefix: string,
  values: string[],
  onRemoveValue: (value: string) => void,
  tone: "default" | "exclude" = "default",
) {
  values.forEach((value) => {
    chips.push({
      id: `${keyPrefix}:${value}`,
      label: `${label}: ${formatOptionLabel(value)}`,
      tone,
      onRemove: () => onRemoveValue(value),
    });
  });
}

function buildAppliedChips(
  state: AggregateExplorerState,
  onRemove: (updater: (current: AggregateExplorerState) => AggregateExplorerState) => void,
): AppliedFilterChip[] {
  const chips: AppliedFilterChip[] = [];
  parseQueryTerms(state.query).forEach((term) => {
    chips.push({
      id: `query:${term}`,
      label: `Search: ${term}`,
      onRemove: () => onRemove((current) => ({ ...current, query: removeQueryTerm(current.query, term) })),
    });
  });
  if (state.from) {
    chips.push({
      id: "from",
      label: `From: ${state.from}`,
      onRemove: () => onRemove((current) => ({ ...current, from: "" })),
    });
  }
  if (state.to) {
    chips.push({
      id: "to",
      label: `To: ${state.to}`,
      onRemove: () => onRemove((current) => ({ ...current, to: "" })),
    });
  }

  appendFacetChips(chips, "SPF", "include-spf", state.includeSpf, (value) =>
    onRemove((current) => ({ ...current, includeSpf: removeValue(current.includeSpf, value) })),
  );
  appendFacetChips(chips, "DKIM", "include-dkim", state.includeDkim, (value) =>
    onRemove((current) => ({ ...current, includeDkim: removeValue(current.includeDkim, value) })),
  );
  appendFacetChips(chips, "Disposition", "include-disposition", state.includeDisposition, (value) =>
    onRemove((current) => ({ ...current, includeDisposition: removeValue(current.includeDisposition, value) })),
  );
  appendFacetChips(chips, "DMARC alignment", "include-dmarc", state.includeDmarcAlignment, (value) =>
    onRemove((current) => ({ ...current, includeDmarcAlignment: removeValue(current.includeDmarcAlignment, value) })),
  );
  appendFacetChips(chips, "DKIM alignment", "include-dkim-align", state.includeDkimAlignment, (value) =>
    onRemove((current) => ({ ...current, includeDkimAlignment: removeValue(current.includeDkimAlignment, value) })),
  );
  appendFacetChips(chips, "SPF alignment", "include-spf-align", state.includeSpfAlignment, (value) =>
    onRemove((current) => ({ ...current, includeSpfAlignment: removeValue(current.includeSpfAlignment, value) })),
  );

  appendFacetChips(
    chips,
    "Not SPF",
    "exclude-spf",
    state.excludeSpf,
    (value) => onRemove((current) => ({ ...current, excludeSpf: removeValue(current.excludeSpf, value) })),
    "exclude",
  );
  appendFacetChips(
    chips,
    "Not DKIM",
    "exclude-dkim",
    state.excludeDkim,
    (value) => onRemove((current) => ({ ...current, excludeDkim: removeValue(current.excludeDkim, value) })),
    "exclude",
  );
  appendFacetChips(
    chips,
    "Not disposition",
    "exclude-disposition",
    state.excludeDisposition,
    (value) => onRemove((current) => ({ ...current, excludeDisposition: removeValue(current.excludeDisposition, value) })),
    "exclude",
  );
  appendFacetChips(
    chips,
    "Not DMARC alignment",
    "exclude-dmarc",
    state.excludeDmarcAlignment,
    (value) => onRemove((current) => ({ ...current, excludeDmarcAlignment: removeValue(current.excludeDmarcAlignment, value) })),
    "exclude",
  );
  appendFacetChips(
    chips,
    "Not DKIM alignment",
    "exclude-dkim-align",
    state.excludeDkimAlignment,
    (value) => onRemove((current) => ({ ...current, excludeDkimAlignment: removeValue(current.excludeDkimAlignment, value) })),
    "exclude",
  );
  appendFacetChips(
    chips,
    "Not SPF alignment",
    "exclude-spf-align",
    state.excludeSpfAlignment,
    (value) => onRemove((current) => ({ ...current, excludeSpfAlignment: removeValue(current.excludeSpfAlignment, value) })),
    "exclude",
  );

  state.grouping.forEach((field, index) => {
    const label = aggregateGroupingOptions.find((option) => option.value === field)?.label ?? field;
    chips.push({
      id: `group:${field}`,
      label: `Group ${index + 1}: ${label}`,
      onRemove: () =>
        onRemove((current) => ({
          ...current,
          grouping: current.grouping.filter((item) => item !== field),
        })),
    });
  });
  return chips;
}

function getDashboardPeriodLabel(state: AggregateExplorerState): string {
  if (state.from && state.to) {
    return `From ${state.from} to ${state.to}`;
  }
  if (state.from) {
    return `From ${state.from}`;
  }
  if (state.to) {
    return `Through ${state.to}`;
  }
  return "All time";
}

function renderMultiValueToggles(values: string[], selectedValues: string[], onToggle: (value: string) => void) {
  return (
    <div className="checkbox-grid">
      {values.map((value) => (
        <label className="checkbox-card" key={value}>
          <input checked={selectedValues.includes(value)} onChange={() => onToggle(value)} type="checkbox" />
          <span>{formatOptionLabel(value)}</span>
        </label>
      ))}
    </div>
  );
}

export function DashboardDetailContent({ dashboardId }: { dashboardId: string }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const initialState = useMemo(() => parseDashboardState(searchParams), [searchParams]);
  const {
    appliedState: currentState,
    commitState,
    draftState,
    resetState: replaceExplorerState,
    updateDraftState,
  } = useAggregateExplorerState<AggregateExplorerState>({
    buildParams: (state) => buildAggregateExplorerParams(state, { includeDomains: false }),
    initialState,
    parseState: parseDashboardState,
    pathname,
    resetKey: dashboardId,
  });
  const [selectedAggregateReportId, setSelectedAggregateReportId] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSharingOpen, setIsSharingOpen] = useState(false);
  const [isOwnershipOpen, setIsOwnershipOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isFiltersOpen, setIsFiltersOpen] = useState(false);
  const [isScopeConfirmOpen, setIsScopeConfirmOpen] = useState(false);
  const [groupToAdd, setGroupToAdd] = useState(aggregateGroupingOptions[0]?.value ?? "domain");
  const [validateMessage, setValidateMessage] = useState<DashboardValidateUpdateResponse | null>(null);
  const [pendingUpdateValues, setPendingUpdateValues] = useState<UpdateDashboardBody | null>(null);
  const availableGroupingOptions = useMemo(
    () => getAvailableAggregateGroupingOptions(draftState.grouping),
    [draftState.grouping],
  );
  const selectedGroupingValue = useMemo(
    () => getSelectedAggregateGroupingValue(draftState.grouping, groupToAdd),
    [draftState.grouping, groupToAdd],
  );

  useEffect(() => {
    if (groupToAdd !== selectedGroupingValue) {
      setGroupToAdd(selectedGroupingValue);
    }
  }, [groupToAdd, selectedGroupingValue]);

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
  const searchBody = useMemo(() => buildAggregateSearchBody(currentState, domainNames), [currentState, domainNames]);
  const groupedRootRequest = useMemo(
    () => buildGroupedSearchBody(currentState, domainNames, { page: currentState.page, pageSize: 20 }),
    [currentState, domainNames],
  );
  const groupedContextKey = useMemo(() => buildAggregateExplorerContextKey(currentState, domainNames), [currentState, domainNames]);

  const flatSearchQuery = useQuery({
    queryKey: ["dashboard-search", dashboardId, searchBody],
    queryFn: () => apiClient.post<SearchRecordsResponse>("/api/v1/search", searchBody),
    enabled: domainNames.length > 0 && currentState.grouping.length === 0,
  });
  const groupedSearchQuery = useQuery({
    queryKey: ["dashboard-search-grouped", dashboardId, groupedRootRequest],
    queryFn: () => apiClient.post<GroupedSearchResponse>("/api/v1/search/grouped", groupedRootRequest),
    enabled: domainNames.length > 0 && currentState.grouping.length > 0,
    placeholderData: keepPreviousData,
  });

  const dashboard = dashboardQuery.data;
  const result = currentState.grouping.length ? groupedSearchQuery.data : flatSearchQuery.data;
  const isGroupedMode = currentState.grouping.length > 0;
  const isGroupedInitialLoading = isGroupedMode && groupedSearchQuery.isPending && !groupedSearchQuery.data;
  const isGroupedRefreshing = isGroupedMode && groupedSearchQuery.isFetching && !!groupedSearchQuery.data;
  const dashboardPeriodLabel = getDashboardPeriodLabel(currentState);
  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.page_size)) : 1;
  const appliedChips = buildAppliedChips(currentState, (updater) => {
    updateDraftState((current) => ({ ...updater(current), page: 1 }));
  });
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

  function applyFilters() {
    commitState((current) => ({ ...current, page: 1 }));
    setIsFiltersOpen(false);
  }

  function resetFilters() {
    const resetState: AggregateExplorerState = { ...defaultAggregateExplorerState };
    replaceExplorerState(resetState);
    setIsFiltersOpen(false);
  }

  function goToPage(page: number) {
    updateDraftState((current) => ({ ...current, page }));
  }

  function handleQuickFilter(option: SearchQuickFilterOption) {
    updateDraftState((current) => {
      const nextState: AggregateExplorerState = { ...current, page: 1 };
      if (option.target === "query") {
        nextState.query = appendQueryValue(current.query, option.value);
      } else if (option.target === "include_spf") {
        nextState.includeSpf = addUniqueValue(current.includeSpf, option.value);
        nextState.excludeSpf = removeValue(current.excludeSpf, option.value);
      } else if (option.target === "exclude_spf") {
        nextState.excludeSpf = addUniqueValue(current.excludeSpf, option.value);
        nextState.includeSpf = removeValue(current.includeSpf, option.value);
      } else if (option.target === "include_dkim") {
        nextState.includeDkim = addUniqueValue(current.includeDkim, option.value);
        nextState.excludeDkim = removeValue(current.excludeDkim, option.value);
      } else if (option.target === "exclude_dkim") {
        nextState.excludeDkim = addUniqueValue(current.excludeDkim, option.value);
        nextState.includeDkim = removeValue(current.includeDkim, option.value);
      } else if (option.target === "include_disposition") {
        nextState.includeDisposition = addUniqueValue(current.includeDisposition, option.value);
        nextState.excludeDisposition = removeValue(current.excludeDisposition, option.value);
      } else if (option.target === "exclude_disposition") {
        nextState.excludeDisposition = addUniqueValue(current.excludeDisposition, option.value);
        nextState.includeDisposition = removeValue(current.includeDisposition, option.value);
      } else if (option.target === "include_dmarc_alignment") {
        nextState.includeDmarcAlignment = addUniqueValue(current.includeDmarcAlignment, option.value);
        nextState.excludeDmarcAlignment = removeValue(current.excludeDmarcAlignment, option.value);
      } else if (option.target === "exclude_dmarc_alignment") {
        nextState.excludeDmarcAlignment = addUniqueValue(current.excludeDmarcAlignment, option.value);
        nextState.includeDmarcAlignment = removeValue(current.includeDmarcAlignment, option.value);
      } else if (option.target === "include_dkim_alignment") {
        nextState.includeDkimAlignment = addUniqueValue(current.includeDkimAlignment, option.value);
        nextState.excludeDkimAlignment = removeValue(current.excludeDkimAlignment, option.value);
      } else if (option.target === "exclude_dkim_alignment") {
        nextState.excludeDkimAlignment = addUniqueValue(current.excludeDkimAlignment, option.value);
        nextState.includeDkimAlignment = removeValue(current.includeDkimAlignment, option.value);
      } else if (option.target === "include_spf_alignment") {
        nextState.includeSpfAlignment = addUniqueValue(current.includeSpfAlignment, option.value);
        nextState.excludeSpfAlignment = removeValue(current.excludeSpfAlignment, option.value);
      } else if (option.target === "exclude_spf_alignment") {
        nextState.excludeSpfAlignment = addUniqueValue(current.excludeSpfAlignment, option.value);
        nextState.includeSpfAlignment = removeValue(current.includeSpfAlignment, option.value);
      }
      return nextState;
    });
  }

  async function loadGroupedBranch(path: GroupPathPart[]) {
    return apiClient.post<GroupedSearchResponse>(
      "/api/v1/search/grouped",
      buildGroupedSearchBody(currentState, domainNames, { path, page: 1, pageSize: 50 }),
    );
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
              flatSearchQuery.refetch();
              groupedSearchQuery.refetch();
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
        <form
          className="search-toolbar"
          onSubmit={(event) => {
            event.preventDefault();
            applyFilters();
          }}
        >
          <label className="field-label">
            Search
            <input
              className="field-input"
              onChange={(event) => updateDraftState((current) => ({ ...current, page: 1, query: event.target.value }), "debounced")}
              placeholder="IP, org, host, or address"
              value={draftState.query}
            />
          </label>
          <label className="field-label">
            From
            <input
              className="field-input"
              onChange={(event) => updateDraftState((current) => ({ ...current, from: event.target.value, page: 1 }), "debounced")}
              type="date"
              value={draftState.from}
            />
          </label>
          <label className="field-label">
            To
            <input
              className="field-input"
              onChange={(event) => updateDraftState((current) => ({ ...current, page: 1, to: event.target.value }), "debounced")}
              type="date"
              value={draftState.to}
            />
          </label>
          <div className="search-toolbar-actions">
            <button className="button-secondary" onClick={() => setIsFiltersOpen(true)} type="button">
              More filters
            </button>
            <button className="button-secondary" onClick={resetFilters} type="button">
              Reset
            </button>
          </div>
        </form>

        <div className="stack" style={{ gap: 12 }}>
            <div className="section-heading">
              <div className="stack" style={{ gap: 6 }}>
                <h2 className="section-title">Grouping</h2>
                <p className="section-intro">Build up to four grouping levels. Group changes update the results and URL immediately.</p>
              </div>
            </div>
            <div className="filter-chip-row">
              {draftState.grouping.length ? (
                draftState.grouping.map((field, index) => {
                  const label = aggregateGroupingOptions.find((option) => option.value === field)?.label ?? field;
                  return (
                    <span className="filter-chip" key={field}>
                      <span>{`${index + 1}. ${label}`}</span>
                    <button
                      aria-label={`Move ${label} earlier`}
                      className="filter-chip-remove"
                      disabled={index === 0}
                      onClick={() =>
                        updateDraftState((current) => {
                          const next = [...current.grouping];
                          [next[index - 1], next[index]] = [next[index], next[index - 1]];
                          return { ...current, grouping: next, page: 1 };
                        })
                      }
                      type="button"
                    >
                      ↑
                    </button>
                    <button
                      aria-label={`Move ${label} later`}
                      className="filter-chip-remove"
                      disabled={index === draftState.grouping.length - 1}
                      onClick={() =>
                        updateDraftState((current) => {
                          const next = [...current.grouping];
                          [next[index], next[index + 1]] = [next[index + 1], next[index]];
                          return { ...current, grouping: next, page: 1 };
                        })
                      }
                      type="button"
                    >
                      ↓
                    </button>
                    <button
                      aria-label={`Remove ${label}`}
                      className="filter-chip-remove"
                      onClick={() =>
                        updateDraftState((current) => ({
                          ...current,
                          grouping: current.grouping.filter((item) => item !== field),
                          page: 1,
                        }))
                      }
                      type="button"
                    >
                      ×
                    </button>
                  </span>
                );
              })
            ) : (
              <span className="status-text">No grouping selected.</span>
            )}
          </div>
          <div className="search-toolbar-actions">
            <label className="field-label">
              Add grouping
              <select
                className="field-input"
                disabled={!availableGroupingOptions.length}
                onChange={(event) => setGroupToAdd(event.target.value)}
                value={selectedGroupingValue}
              >
                {availableGroupingOptions.length ? (
                  availableGroupingOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))
                ) : (
                  <option value="">No levels available</option>
                )}
              </select>
            </label>
            <button
              className="button-secondary"
              disabled={!selectedGroupingValue || draftState.grouping.length >= 4}
              onClick={() =>
                updateDraftState((current) => ({
                  ...current,
                  grouping: current.grouping.length >= 4 || !selectedGroupingValue ? current.grouping : [...current.grouping, selectedGroupingValue],
                  page: 1,
                }))
              }
              type="button"
            >
              Add level
            </button>
          </div>
        </div>
      </section>

      <section className="surface-card stack">
        <div className="section-heading">
          <div className="stack" style={{ gap: 8 }}>
            <h2 className="section-title">Live results</h2>
            <p className="section-intro">Review the current aggregate records for the domains in this dashboard.</p>
            <p className="status-text">{`Dashboard period: ${dashboardPeriodLabel}`}</p>
          </div>
          {appliedChips.length ? (
            <button className="button-secondary" onClick={resetFilters} type="button">
              Clear all
            </button>
          ) : null}
        </div>
        {appliedChips.length ? (
          <div className="filter-chip-row">
            {appliedChips.map((chip) => (
              <span className={`filter-chip${chip.tone === "exclude" ? " filter-chip-exclude" : ""}`} key={chip.id}>
                <span>{chip.label}</span>
                <button aria-label={`Remove ${chip.label}`} className="filter-chip-remove" onClick={chip.onRemove} type="button">
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}
        {dashboard && !domainNames.length ? <p className="status-text">This dashboard has no domains in scope.</p> : null}
        {currentState.grouping.length ? (
          isGroupedInitialLoading ? <p className="status-text">Loading live dashboard results...</p> : null
        ) : flatSearchQuery.isLoading ? (
          <p className="status-text">Loading live dashboard results...</p>
        ) : null}
        {isGroupedRefreshing ? <p className="status-text">Updating grouped results...</p> : null}
        {currentState.grouping.length ? (
          groupedSearchQuery.error ? <p className="error-text">{groupedSearchQuery.error instanceof Error ? groupedSearchQuery.error.message : "Failed to load dashboard results"}</p> : null
        ) : flatSearchQuery.error ? (
          <p className="error-text">{flatSearchQuery.error instanceof Error ? flatSearchQuery.error.message : "Failed to load dashboard results"}</p>
        ) : null}
        {result && !currentState.grouping.length ? (
          <AggregateSearchResultsTable
            emptyMessage="No matching records yet for this dashboard scope."
            onQuickFilter={handleQuickFilter}
            onViewReport={setSelectedAggregateReportId}
            result={result as SearchRecordsResponse}
            visibleColumns={dashboard?.visible_columns}
          />
        ) : null}
        {result && currentState.grouping.length ? (
          <GroupedAggregateResultsTable
            contextKey={groupedContextKey}
            emptyMessage="No grouped dashboard results yet for this scope."
            grouping={currentState.grouping}
            initialResult={result as GroupedSearchResponse}
            loadBranch={loadGroupedBranch}
            onQuickFilter={handleQuickFilter}
            onViewReport={setSelectedAggregateReportId}
            showPeriodColumn={false}
            showSummaryCounts={false}
            visibleColumns={dashboard?.visible_columns}
          />
        ) : null}
        {result ? (
          <div className="pagination-row">
            <span className="status-text">
              Page {result.page} of {totalPages}
            </span>
            <div style={{ display: "flex", gap: 12 }}>
              <button className="button-secondary" disabled={currentState.page <= 1} onClick={() => goToPage(Math.max(1, currentState.page - 1))} type="button">
                Previous
              </button>
              <button className="button-secondary" disabled={currentState.page >= totalPages} onClick={() => goToPage(currentState.page + 1)} type="button">
                Next
              </button>
            </div>
          </div>
        ) : null}
      </section>
      <SlideOverPanel
        description="Refine the dashboard with include/exclude facets. Changes apply instantly and stay in the URL."
        onClose={() => setIsFiltersOpen(false)}
        open={isFiltersOpen}
        title="More filters"
      >
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            applyFilters();
          }}
        >
          <div className="stack" style={{ gap: 10 }}>
            <p className="stat-label">Include SPF</p>
            {renderMultiValueToggles(resultOptions, draftState.includeSpf, (value) =>
              updateDraftState((current) => ({
                ...current,
                includeSpf: toggleValue(current.includeSpf, value),
                excludeSpf: removeValue(current.excludeSpf, value),
                page: 1,
              })),
            )}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <p className="stat-label">Exclude SPF</p>
            {renderMultiValueToggles(resultOptions, draftState.excludeSpf, (value) =>
              updateDraftState((current) => ({
                ...current,
                excludeSpf: toggleValue(current.excludeSpf, value),
                includeSpf: removeValue(current.includeSpf, value),
                page: 1,
              })),
            )}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <p className="stat-label">Include DKIM</p>
            {renderMultiValueToggles(resultOptions, draftState.includeDkim, (value) =>
              updateDraftState((current) => ({
                ...current,
                includeDkim: toggleValue(current.includeDkim, value),
                excludeDkim: removeValue(current.excludeDkim, value),
                page: 1,
              })),
            )}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <p className="stat-label">Exclude DKIM</p>
            {renderMultiValueToggles(resultOptions, draftState.excludeDkim, (value) =>
              updateDraftState((current) => ({
                ...current,
                excludeDkim: toggleValue(current.excludeDkim, value),
                includeDkim: removeValue(current.includeDkim, value),
                page: 1,
              })),
            )}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <p className="stat-label">Include disposition</p>
            {renderMultiValueToggles(dispositionOptions, draftState.includeDisposition, (value) =>
              updateDraftState((current) => ({
                ...current,
                includeDisposition: toggleValue(current.includeDisposition, value),
                excludeDisposition: removeValue(current.excludeDisposition, value),
                page: 1,
              })),
            )}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <p className="stat-label">Exclude disposition</p>
            {renderMultiValueToggles(dispositionOptions, draftState.excludeDisposition, (value) =>
              updateDraftState((current) => ({
                ...current,
                excludeDisposition: toggleValue(current.excludeDisposition, value),
                includeDisposition: removeValue(current.includeDisposition, value),
                page: 1,
              })),
            )}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <p className="stat-label">Include DMARC alignment</p>
            {renderMultiValueToggles(dmarcAlignmentOptions, draftState.includeDmarcAlignment, (value) =>
              updateDraftState((current) => ({
                ...current,
                includeDmarcAlignment: toggleValue(current.includeDmarcAlignment, value),
                excludeDmarcAlignment: removeValue(current.excludeDmarcAlignment, value),
                page: 1,
              })),
            )}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <p className="stat-label">Exclude DMARC alignment</p>
            {renderMultiValueToggles(dmarcAlignmentOptions, draftState.excludeDmarcAlignment, (value) =>
              updateDraftState((current) => ({
                ...current,
                excludeDmarcAlignment: toggleValue(current.excludeDmarcAlignment, value),
                includeDmarcAlignment: removeValue(current.includeDmarcAlignment, value),
                page: 1,
              })),
            )}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <p className="stat-label">Include DKIM alignment</p>
            {renderMultiValueToggles(alignmentModeOptions, draftState.includeDkimAlignment, (value) =>
              updateDraftState((current) => ({
                ...current,
                includeDkimAlignment: toggleValue(current.includeDkimAlignment, value),
                excludeDkimAlignment: removeValue(current.excludeDkimAlignment, value),
                page: 1,
              })),
            )}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <p className="stat-label">Exclude DKIM alignment</p>
            {renderMultiValueToggles(alignmentModeOptions, draftState.excludeDkimAlignment, (value) =>
              updateDraftState((current) => ({
                ...current,
                excludeDkimAlignment: toggleValue(current.excludeDkimAlignment, value),
                includeDkimAlignment: removeValue(current.includeDkimAlignment, value),
                page: 1,
              })),
            )}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <p className="stat-label">Include SPF alignment</p>
            {renderMultiValueToggles(alignmentModeOptions, draftState.includeSpfAlignment, (value) =>
              updateDraftState((current) => ({
                ...current,
                includeSpfAlignment: toggleValue(current.includeSpfAlignment, value),
                excludeSpfAlignment: removeValue(current.excludeSpfAlignment, value),
                page: 1,
              })),
            )}
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <p className="stat-label">Exclude SPF alignment</p>
            {renderMultiValueToggles(alignmentModeOptions, draftState.excludeSpfAlignment, (value) =>
              updateDraftState((current) => ({
                ...current,
                excludeSpfAlignment: toggleValue(current.excludeSpfAlignment, value),
                includeSpfAlignment: removeValue(current.includeSpfAlignment, value),
                page: 1,
              })),
            )}
          </div>
          <div className="search-toolbar-actions">
            <button className="button-secondary" onClick={() => setIsFiltersOpen(false)} type="button">
              Done
            </button>
          </div>
        </form>
      </SlideOverPanel>
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
