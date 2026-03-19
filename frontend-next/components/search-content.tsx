"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePathname, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ReportDetailModal } from "@/components/report-detail-modal";
import {
  AggregateSearchResultsTable,
  ForensicResultsTable,
  GroupedAggregateResultsTable,
  type SearchQuickFilterOption,
} from "@/components/search-results-table";
import { SlideOverPanel } from "@/components/slide-over-panel";
import { apiClient } from "@/lib/api/client";
import {
  addUniqueValue,
  aggregateGroupingOptions,
  appendQueryValue,
  buildAggregateExplorerParams,
  buildAggregateSearchBody,
  buildGroupedSearchBody,
  defaultAggregateExplorerState,
  formatOptionLabel,
  getAvailableAggregateGroupingOptions,
  getSelectedAggregateGroupingValue,
  parseAggregateExplorerState,
  removeValue,
  toggleValue,
  type AggregateExplorerState,
} from "@/lib/aggregate-explorer-state";
import { useAggregateExplorerState } from "@/lib/use-aggregate-explorer-state";
import type {
  DomainSummary,
  DomainsResponse,
  ForensicReportsResponse,
  GroupPathPart,
  GroupedSearchResponse,
  SearchRecordsResponse,
} from "@/lib/api/types";
import { buildSearchParams } from "@/lib/url-state";

type SearchReportType = "aggregate" | "forensic";

type SearchState = AggregateExplorerState & {
  reportType: SearchReportType;
};

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
function parseSearchState(searchParams: URLSearchParams): SearchState {
  return {
    reportType: searchParams.get("report_type") === "forensic" ? "forensic" : "aggregate",
    ...parseAggregateExplorerState(searchParams, { includeDomains: true }),
  };
}

function buildSearchRouteParams(state: SearchState): string {
  return buildAggregateExplorerParams(state, {
    includeDomains: true,
    extraParams: {
      report_type: state.reportType !== "aggregate" ? state.reportType : "",
    },
  });
}

function buildForensicPath(state: SearchState): string {
  const params = buildSearchParams({
    domains: state.domains.length ? state.domains.join(",") : "",
    from: state.from,
    to: state.to,
    page: String(state.page),
    page_size: "10",
  });
  return params ? `/api/v1/reports/forensic?${params}` : "/api/v1/reports/forensic";
}

function getDomainSummaryLabel(selectedCount: number, totalCount: number): string {
  if (!totalCount) {
    return "No domains";
  }
  if (!selectedCount) {
    return `All visible domains available (${totalCount})`;
  }
  if (selectedCount === 1) {
    return "1 domain selected";
  }
  return `${selectedCount} domains selected`;
}

function hasAggregateCriteria(state: AggregateExplorerState): boolean {
  return !!(
    state.domains.length ||
    state.query ||
    state.from ||
    state.to ||
    state.includeDmarcAlignment.length ||
    state.includeDkimAlignment.length ||
    state.includeSpfAlignment.length ||
    state.includeSpf.length ||
    state.includeDkim.length ||
    state.includeDisposition.length ||
    state.excludeDmarcAlignment.length ||
    state.excludeDkimAlignment.length ||
    state.excludeSpfAlignment.length ||
    state.excludeSpf.length ||
    state.excludeDkim.length ||
    state.excludeDisposition.length
  );
}

function buildAppliedChips(
  state: SearchState,
  onRemove: (updater: (current: SearchState) => SearchState) => void,
): AppliedFilterChip[] {
  const chips: AppliedFilterChip[] = [];

  state.domains.forEach((domain) => {
    chips.push({
      id: `domain:${domain}`,
      label: `Domain: ${domain}`,
      onRemove: () => onRemove((current) => ({ ...current, domains: current.domains.filter((item) => item !== domain) })),
    });
  });

  if (state.query) {
    chips.push({
      id: "query",
      label: `Search: ${state.query}`,
      onRemove: () => onRemove((current) => ({ ...current, query: "" })),
    });
  }
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
  appendFacetChips(chips, "DMARC alignment", "include-dmarc-alignment", state.includeDmarcAlignment, (value) =>
    onRemove((current) => ({ ...current, includeDmarcAlignment: removeValue(current.includeDmarcAlignment, value) })),
  );
  appendFacetChips(chips, "DKIM alignment", "include-dkim-alignment", state.includeDkimAlignment, (value) =>
    onRemove((current) => ({ ...current, includeDkimAlignment: removeValue(current.includeDkimAlignment, value) })),
  );
  appendFacetChips(chips, "SPF alignment", "include-spf-alignment", state.includeSpfAlignment, (value) =>
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
    "exclude-dmarc-alignment",
    state.excludeDmarcAlignment,
    (value) => onRemove((current) => ({ ...current, excludeDmarcAlignment: removeValue(current.excludeDmarcAlignment, value) })),
    "exclude",
  );
  appendFacetChips(
    chips,
    "Not DKIM alignment",
    "exclude-dkim-alignment",
    state.excludeDkimAlignment,
    (value) => onRemove((current) => ({ ...current, excludeDkimAlignment: removeValue(current.excludeDkimAlignment, value) })),
    "exclude",
  );
  appendFacetChips(
    chips,
    "Not SPF alignment",
    "exclude-spf-alignment",
    state.excludeSpfAlignment,
    (value) => onRemove((current) => ({ ...current, excludeSpfAlignment: removeValue(current.excludeSpfAlignment, value) })),
    "exclude",
  );

  state.grouping.forEach((field, index) => {
    const label = aggregateGroupingOptions.find((option) => option.value === field)?.label ?? field;
    chips.push({
      id: `grouping:${field}`,
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

function renderMultiValueToggles(
  values: string[],
  selectedValues: string[],
  onToggle: (value: string) => void,
) {
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

export function SearchContent() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const initialState = useMemo(() => parseSearchState(searchParams), [searchParams]);
  const {
    appliedState: currentState,
    commitState,
    draftState,
    resetState: replaceExplorerState,
    setDraftOnly,
    updateDraftState,
  } = useAggregateExplorerState<SearchState>({
    buildParams: buildSearchRouteParams,
    initialState,
    parseState: parseSearchState,
    pathname,
    resetKey: pathname,
  });
  const [isFiltersOpen, setIsFiltersOpen] = useState(false);
  const [selectedAggregateReportId, setSelectedAggregateReportId] = useState<string | null>(null);
  const [selectedForensicReportId, setSelectedForensicReportId] = useState<string | null>(null);
  const [groupToAdd, setGroupToAdd] = useState(aggregateGroupingOptions[0]?.value ?? "domain");
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

  const domainsQuery = useQuery({
    queryKey: ["domains"],
    queryFn: () => apiClient.get<DomainsResponse>("/api/v1/domains"),
  });

  const aggregateRequest = useMemo(() => buildAggregateSearchBody(currentState, currentState.domains), [currentState]);
  const groupedRootRequest = useMemo(
    () => buildGroupedSearchBody(currentState, currentState.domains, { page: currentState.page, pageSize: 20 }),
    [currentState],
  );
  const forensicPath = useMemo(() => buildForensicPath(currentState), [currentState]);
  const hasAppliedSearch = currentState.reportType === "aggregate" ? hasAggregateCriteria(currentState) : !!(currentState.domains.length || currentState.from || currentState.to);

  const aggregateQuery = useQuery({
    queryKey: ["search", "aggregate", aggregateRequest],
    queryFn: () => apiClient.post<SearchRecordsResponse>("/api/v1/search", aggregateRequest),
    enabled: currentState.reportType === "aggregate" && hasAppliedSearch && currentState.grouping.length === 0,
  });

  const groupedQuery = useQuery({
    queryKey: ["search", "aggregate-grouped", groupedRootRequest],
    queryFn: () => apiClient.post<GroupedSearchResponse>("/api/v1/search/grouped", groupedRootRequest),
    enabled: currentState.reportType === "aggregate" && hasAppliedSearch && currentState.grouping.length > 0,
  });

  const forensicQuery = useQuery({
    queryKey: ["search", "forensic", forensicPath],
    queryFn: () => apiClient.get<ForensicReportsResponse>(forensicPath),
    enabled: currentState.reportType === "forensic" && hasAppliedSearch,
  });

  const aggregateResult = aggregateQuery.data;
  const groupedResult = groupedQuery.data;
  const forensicResult = forensicQuery.data;
  const activeResult = currentState.reportType === "forensic" ? forensicResult : currentState.grouping.length ? groupedResult : aggregateResult;
  const isLoading =
    currentState.reportType === "forensic" ? forensicQuery.isLoading : currentState.grouping.length ? groupedQuery.isLoading : aggregateQuery.isLoading;
  const error =
    currentState.reportType === "forensic" ? forensicQuery.error : currentState.grouping.length ? groupedQuery.error : aggregateQuery.error;
  const totalPages = activeResult ? Math.max(1, Math.ceil(activeResult.total / activeResult.page_size)) : 1;
  const domains = domainsQuery.data?.domains ?? [];
  const appliedChips = buildAppliedChips(currentState, (updater) => {
    updateDraftState((current) => ({ ...updater(current), page: 1 }));
  });

  function updateSearchDraft(
    updater: SearchState | ((current: SearchState) => SearchState),
    mode: "immediate" | "debounced" = "immediate",
  ) {
    if (draftState.reportType === "aggregate") {
      return updateDraftState(updater, mode);
    }
    return setDraftOnly(updater);
  }

  function applySearch() {
    commitState((current) => ({ ...current, page: 1 }));
    setIsFiltersOpen(false);
  }

  function resetSearch() {
    const nextState: SearchState = {
      ...defaultAggregateExplorerState,
      reportType: draftState.reportType,
    };
    replaceExplorerState(nextState);
    setIsFiltersOpen(false);
  }

  function goToPage(page: number) {
    if (currentState.reportType === "aggregate") {
      updateDraftState((current) => ({ ...current, page }));
      return;
    }
    replaceExplorerState({ ...currentState, page });
  }

  function handleQuickFilter(option: SearchQuickFilterOption) {
    updateDraftState((current) => {
      const nextState: SearchState = { ...current, page: 1 };
      if (option.target === "domains") {
        nextState.domains = addUniqueValue(current.domains, option.value);
      } else if (option.target === "query") {
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
      buildGroupedSearchBody(currentState, currentState.domains, { path, page: 1, pageSize: 50 }),
    );
  }

  const resultsSummary =
    !hasAppliedSearch
      ? currentState.reportType === "aggregate"
        ? "Start with a query, domain, date, or advanced filter to avoid broad random-looking result lists."
        : "Pick a domain or date range before loading forensic reports."
      : activeResult
        ? `Showing ${activeResult.items.length} of ${activeResult.total} ${currentState.reportType === "aggregate" ? "matching records or groups" : "reports"}.`
        : "Review the current results for the domains you can access.";

  return (
    <AppShell
      title="Search"
      description="Review aggregate and forensic reports across the domains you can access."
      actions={
        <button
          className="button-secondary"
          onClick={() => {
            domainsQuery.refetch();
            if (hasAppliedSearch) {
              aggregateQuery.refetch();
              groupedQuery.refetch();
              forensicQuery.refetch();
            }
          }}
          type="button"
        >
          Refresh
        </button>
      }
    >
      <section className="surface-card stack">
        <form
          className="search-toolbar"
          onSubmit={(event) => {
            event.preventDefault();
            applySearch();
          }}
        >
          <label className="field-label">
            Report type
            <select
              className="field-input"
              onChange={(event) => {
                const nextReportType = event.target.value === "forensic" ? "forensic" : "aggregate";
                const updater = (current: SearchState): SearchState => ({
                  ...defaultAggregateExplorerState,
                  reportType: nextReportType,
                  domains: current.domains,
                  from: current.from,
                  to: current.to,
                });
                if (nextReportType === "aggregate") {
                  updateDraftState(updater);
                  return;
                }
                setDraftOnly(updater);
              }}
              value={draftState.reportType}
            >
              <option value="aggregate">Aggregate</option>
              <option value="forensic">Forensic</option>
            </select>
          </label>
          <label className="field-label">
            Free-text search
            <input
              className="field-input"
              disabled={draftState.reportType === "forensic"}
              onChange={(event) =>
                updateSearchDraft((current) => ({ ...current, page: 1, query: event.target.value }), "debounced")
              }
              placeholder={draftState.reportType === "forensic" ? "Forensic reports use domain or date filters" : "IP, org, host, or address"}
              value={draftState.query}
            />
          </label>
          <label className="field-label">
            From
            <input
              className="field-input"
              onChange={(event) =>
                updateSearchDraft((current) => ({ ...current, from: event.target.value, page: 1 }), "debounced")
              }
              type="date"
              value={draftState.from}
            />
          </label>
          <label className="field-label">
            To
            <input
              className="field-input"
              onChange={(event) =>
                updateSearchDraft((current) => ({ ...current, page: 1, to: event.target.value }), "debounced")
              }
              type="date"
              value={draftState.to}
            />
          </label>
          <div className="search-toolbar-actions">
            {draftState.reportType === "aggregate" ? (
              <button className="button-secondary" onClick={() => setIsFiltersOpen(true)} type="button">
                More filters
              </button>
            ) : (
              <button className="button-primary" type="submit">
                Search
              </button>
            )}
            <button className="button-secondary" onClick={resetSearch} type="button">
              Reset
            </button>
          </div>
        </form>

        <div className="search-domain-picker">
          <span className="field-label" style={{ gap: 0 }}>
            Domains
          </span>
          {domainsQuery.isLoading ? <p className="status-text">Loading visible domains...</p> : null}
          {!domainsQuery.isLoading && !domains.length ? <p className="status-text">No visible domains are available for this account yet.</p> : null}
          {domains.length ? (
            <div className="search-domain-grid">
              {domains.map((domain: DomainSummary) => (
                <label className="checkbox-card" key={domain.id}>
                  <input
                    checked={draftState.domains.includes(domain.name)}
                    onChange={() =>
                      updateSearchDraft((current) => ({ ...current, domains: toggleValue(current.domains, domain.name), page: 1 }))
                    }
                    type="checkbox"
                  />
                  <span>{domain.name}</span>
                </label>
              ))}
            </div>
          ) : null}
        </div>

        {draftState.reportType === "aggregate" ? (
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
        ) : null}

        <div className="search-toolbar-meta">
          <span className="status-text">{getDomainSummaryLabel(draftState.domains.length, domains.length)}</span>
          {draftState.reportType === "aggregate" ? (
            <span className="status-text">Use at least one filter before loading aggregate results.</span>
          ) : (
            <span className="status-text">Forensic reports require a domain or date filter before loading.</span>
          )}
        </div>
      </section>

      <section className="surface-card stack">
        <div className="section-heading">
          <div className="stack" style={{ gap: 8 }}>
            <h2 className="section-title">{currentState.reportType === "aggregate" ? "Results" : "Forensic reports"}</h2>
            <p className="section-intro">{resultsSummary}</p>
          </div>
          {appliedChips.length ? (
            <button className="button-secondary" onClick={resetSearch} type="button">
              Clear all
            </button>
          ) : null}
        </div>
        {appliedChips.length ? (
          <div className="filter-chip-row">
            {currentState.reportType === "forensic" ? <span className="filter-chip">Mode: Forensic</span> : null}
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
        {!hasAppliedSearch ? <p className="status-text">Nothing is loaded yet. Add a query, domain, date range, or advanced filter and the results will update here.</p> : null}
        {hasAppliedSearch && isLoading ? <p className="status-text">Loading results...</p> : null}
        {hasAppliedSearch && error ? <p className="error-text">{error instanceof Error ? error.message : "Failed to load results"}</p> : null}
        {domainsQuery.error ? <p className="error-text">{domainsQuery.error instanceof Error ? domainsQuery.error.message : "Failed to load visible domains"}</p> : null}
        {hasAppliedSearch && aggregateResult && currentState.reportType === "aggregate" && !currentState.grouping.length ? (
          <AggregateSearchResultsTable emptyMessage="No aggregate results found." onQuickFilter={handleQuickFilter} onViewReport={setSelectedAggregateReportId} result={aggregateResult} />
        ) : null}
        {hasAppliedSearch && groupedResult && currentState.reportType === "aggregate" && currentState.grouping.length ? (
          <GroupedAggregateResultsTable
            emptyMessage="No grouped aggregate results found."
            grouping={currentState.grouping}
            initialResult={groupedResult}
            loadBranch={loadGroupedBranch}
            onQuickFilter={handleQuickFilter}
            onViewReport={setSelectedAggregateReportId}
          />
        ) : null}
        {hasAppliedSearch && forensicResult && currentState.reportType === "forensic" ? (
          <ForensicResultsTable emptyMessage="No forensic reports found." onQuickFilter={handleQuickFilter} onViewReport={setSelectedForensicReportId} result={forensicResult} />
        ) : null}
        {hasAppliedSearch && activeResult ? (
          <div className="pagination-row">
            <span className="status-text">
              Page {activeResult.page} of {totalPages}
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
        description="Refine aggregate searches with include/exclude facets. Changes apply instantly and stay in the URL."
        onClose={() => setIsFiltersOpen(false)}
        open={isFiltersOpen}
        title="More filters"
      >
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            applySearch();
          }}
        >
          {draftState.reportType === "aggregate" ? (
            <>
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
            </>
          ) : null}
          <div className="search-toolbar-actions">
            <button className="button-secondary" onClick={() => setIsFiltersOpen(false)} type="button">
              Done
            </button>
          </div>
        </form>
      </SlideOverPanel>

      {selectedAggregateReportId ? <ReportDetailModal kind="aggregate" onClose={() => setSelectedAggregateReportId(null)} reportId={selectedAggregateReportId} /> : null}
      {selectedForensicReportId ? <ReportDetailModal kind="forensic" onClose={() => setSelectedForensicReportId(null)} reportId={selectedForensicReportId} /> : null}
    </AppShell>
  );
}
