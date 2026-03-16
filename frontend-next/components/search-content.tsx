"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ReportDetailModal } from "@/components/report-detail-modal";
import {
  AggregateSearchResultsTable,
  ForensicResultsTable,
  type SearchQuickFilterOption,
} from "@/components/search-results-table";
import { SlideOverPanel } from "@/components/slide-over-panel";
import { apiClient } from "@/lib/api/client";
import type {
  DomainSummary,
  DomainsResponse,
  ForensicReportsResponse,
  SearchRecordsBody,
  SearchRecordsResponse,
} from "@/lib/api/types";
import { buildSearchParams, parseIntegerParam, parseStringParam } from "@/lib/url-state";

type SearchReportType = "aggregate" | "forensic";

type SearchState = {
  reportType: SearchReportType;
  domains: string[];
  query: string;
  from: string;
  to: string;
  includeSpf: string;
  includeDkim: string;
  includeDisposition: string;
  excludeSpf: string;
  excludeDkim: string;
  excludeDisposition: string;
  page: number;
};

type AppliedFilterChip = {
  id: string;
  label: string;
  tone?: "default" | "exclude";
  onRemove: () => void;
};

const defaultSearchState: SearchState = {
  reportType: "aggregate",
  domains: [],
  query: "",
  from: "",
  to: "",
  includeSpf: "",
  includeDkim: "",
  includeDisposition: "",
  excludeSpf: "",
  excludeDkim: "",
  excludeDisposition: "",
  page: 1,
};

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

function parseDomainsParam(value: string | null): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseSearchState(searchParams: URLSearchParams): SearchState {
  const reportType = searchParams.get("report_type") === "forensic" ? "forensic" : "aggregate";
  return {
    reportType,
    domains: parseDomainsParam(searchParams.get("domains")),
    query: parseStringParam(searchParams.get("query")),
    from: parseStringParam(searchParams.get("from")),
    to: parseStringParam(searchParams.get("to")),
    includeSpf: parseStringParam(searchParams.get("include_spf")),
    includeDkim: parseStringParam(searchParams.get("include_dkim")),
    includeDisposition: parseStringParam(searchParams.get("include_disposition")),
    excludeSpf: parseStringParam(searchParams.get("exclude_spf")),
    excludeDkim: parseStringParam(searchParams.get("exclude_dkim")),
    excludeDisposition: parseStringParam(searchParams.get("exclude_disposition")),
    page: parseIntegerParam(searchParams.get("page"), 1),
  };
}

function buildSearchRouteParams(state: SearchState): string {
  return buildSearchParams({
    report_type: state.reportType !== "aggregate" ? state.reportType : "",
    domains: state.domains.length ? state.domains.join(",") : "",
    query: state.query,
    from: state.from,
    to: state.to,
    include_spf: state.reportType === "aggregate" ? state.includeSpf : "",
    include_dkim: state.reportType === "aggregate" ? state.includeDkim : "",
    include_disposition: state.reportType === "aggregate" ? state.includeDisposition : "",
    exclude_spf: state.reportType === "aggregate" ? state.excludeSpf : "",
    exclude_dkim: state.reportType === "aggregate" ? state.excludeDkim : "",
    exclude_disposition: state.reportType === "aggregate" ? state.excludeDisposition : "",
    page: state.page > 1 ? String(state.page) : "",
  });
}

function buildAggregateRequest(state: SearchState): SearchRecordsBody {
  const include: Record<string, string[]> = {};
  const exclude: Record<string, string[]> = {};

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
  if (state.excludeDkim) {
    exclude.dkim_result = [state.excludeDkim];
  }
  if (state.excludeDisposition) {
    exclude.disposition = [state.excludeDisposition];
  }

  return {
    domains: state.domains.length ? state.domains : undefined,
    query: state.query || undefined,
    from: state.from || undefined,
    to: state.to || undefined,
    include: Object.keys(include).length ? include : undefined,
    exclude: Object.keys(exclude).length ? exclude : undefined,
    page: state.page,
    page_size: 10,
  };
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

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function appendQueryValue(query: string, value: string): string {
  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return query;
  }
  const parts = query
    .split(/\s+/)
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.includes(trimmedValue)) {
    return query;
  }
  return [...parts, trimmedValue].join(" ");
}

function formatOptionLabel(value: string): string {
  if (!value) {
    return value;
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function getDomainSummaryLabel(selectedCount: number, totalCount: number): string {
  if (!totalCount) {
    return "No domains";
  }
  if (!selectedCount) {
    return `All visible domains (${totalCount})`;
  }
  if (selectedCount === 1) {
    return "1 domain selected";
  }
  return `${selectedCount} domains selected`;
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
      onRemove: () => onRemove((current) => ({ ...current, domains: current.domains.filter((entry) => entry !== domain) })),
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
  if (state.includeSpf) {
    chips.push({
      id: "include-spf",
      label: `SPF: ${formatOptionLabel(state.includeSpf)}`,
      onRemove: () => onRemove((current) => ({ ...current, includeSpf: "" })),
    });
  }
  if (state.excludeSpf) {
    chips.push({
      id: "exclude-spf",
      label: `Not SPF: ${formatOptionLabel(state.excludeSpf)}`,
      tone: "exclude",
      onRemove: () => onRemove((current) => ({ ...current, excludeSpf: "" })),
    });
  }
  if (state.includeDkim) {
    chips.push({
      id: "include-dkim",
      label: `DKIM: ${formatOptionLabel(state.includeDkim)}`,
      onRemove: () => onRemove((current) => ({ ...current, includeDkim: "" })),
    });
  }
  if (state.excludeDkim) {
    chips.push({
      id: "exclude-dkim",
      label: `Not DKIM: ${formatOptionLabel(state.excludeDkim)}`,
      tone: "exclude",
      onRemove: () => onRemove((current) => ({ ...current, excludeDkim: "" })),
    });
  }
  if (state.includeDisposition) {
    chips.push({
      id: "include-disposition",
      label: `Disposition: ${formatOptionLabel(state.includeDisposition)}`,
      onRemove: () => onRemove((current) => ({ ...current, includeDisposition: "" })),
    });
  }
  if (state.excludeDisposition) {
    chips.push({
      id: "exclude-disposition",
      label: `Not disposition: ${formatOptionLabel(state.excludeDisposition)}`,
      tone: "exclude",
      onRemove: () => onRemove((current) => ({ ...current, excludeDisposition: "" })),
    });
  }

  return chips;
}

export function SearchContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const currentState = useMemo(() => parseSearchState(searchParams), [searchParams]);
  const [draftState, setDraftState] = useState<SearchState>(currentState);
  const [isFiltersOpen, setIsFiltersOpen] = useState(false);
  const [selectedAggregateReportId, setSelectedAggregateReportId] = useState<string | null>(null);
  const [selectedForensicReportId, setSelectedForensicReportId] = useState<string | null>(null);

  useEffect(() => {
    setDraftState(currentState);
  }, [currentState]);

  const domainsQuery = useQuery({
    queryKey: ["domains"],
    queryFn: () => apiClient.get<DomainsResponse>("/api/v1/domains"),
  });

  const aggregateRequest = useMemo(() => buildAggregateRequest(currentState), [currentState]);
  const forensicPath = useMemo(() => buildForensicPath(currentState), [currentState]);

  const aggregateQuery = useQuery({
    queryKey: ["search", "aggregate", aggregateRequest],
    queryFn: () => apiClient.post<SearchRecordsResponse>("/api/v1/search", aggregateRequest),
    enabled: currentState.reportType === "aggregate",
  });

  const forensicQuery = useQuery({
    queryKey: ["search", "forensic", forensicPath],
    queryFn: () => apiClient.get<ForensicReportsResponse>(forensicPath),
    enabled: currentState.reportType === "forensic",
  });

  const aggregateResult = aggregateQuery.data;
  const forensicResult = forensicQuery.data;
  const activeResult = currentState.reportType === "aggregate" ? aggregateResult : forensicResult;
  const isLoading = currentState.reportType === "aggregate" ? aggregateQuery.isLoading : forensicQuery.isLoading;
  const error = currentState.reportType === "aggregate" ? aggregateQuery.error : forensicQuery.error;
  const totalPages = activeResult ? Math.max(1, Math.ceil(activeResult.total / activeResult.page_size)) : 1;
  const domains = domainsQuery.data?.domains ?? [];
  const appliedChips = buildAppliedChips(currentState, (updater) => {
    const nextState = updater(currentState);
    updateUrl({ ...nextState, page: 1 });
  });
  const hasAppliedFilters = appliedChips.length > 0 || currentState.reportType !== "aggregate";
  const resultsSummary = activeResult
    ? `Showing ${activeResult.items.length} of ${activeResult.total} ${currentState.reportType === "aggregate" ? "matching records" : "reports"}.`
    : currentState.reportType === "aggregate"
      ? "Search aggregate records across your visible domains."
      : "Review forensic reports for the domains you can access.";

  function updateUrl(state: SearchState) {
    const nextParams = buildSearchRouteParams(state);
    router.replace(nextParams ? `${pathname}?${nextParams}` : pathname);
  }

  function applySearch() {
    updateUrl({ ...draftState, page: 1 });
    setIsFiltersOpen(false);
  }

  function resetSearch() {
    setDraftState(defaultSearchState);
    updateUrl(defaultSearchState);
    setIsFiltersOpen(false);
  }

  function goToPage(page: number) {
    updateUrl({ ...currentState, page });
  }

  function handleQuickFilter(option: SearchQuickFilterOption) {
    const nextState = { ...currentState, page: 1 };

    if (option.target === "domains") {
      nextState.domains = currentState.domains.includes(option.value)
        ? currentState.domains
        : [...currentState.domains, option.value];
    } else if (option.target === "query") {
      nextState.query = appendQueryValue(currentState.query, option.value);
    } else if (option.target === "include_spf") {
      nextState.includeSpf = option.value;
      nextState.excludeSpf = "";
    } else if (option.target === "exclude_spf") {
      nextState.excludeSpf = option.value;
      nextState.includeSpf = "";
    } else if (option.target === "include_dkim") {
      nextState.includeDkim = option.value;
      nextState.excludeDkim = "";
    } else if (option.target === "exclude_dkim") {
      nextState.excludeDkim = option.value;
      nextState.includeDkim = "";
    } else if (option.target === "include_disposition") {
      nextState.includeDisposition = option.value;
      nextState.excludeDisposition = "";
    } else if (option.target === "exclude_disposition") {
      nextState.excludeDisposition = option.value;
      nextState.includeDisposition = "";
    }

    setDraftState(nextState);
    updateUrl(nextState);
  }

  return (
    <AppShell
      title="Search"
      description="Review aggregate and forensic reports across the domains you can access."
      actions={
        <button
          className="button-secondary"
          onClick={() => {
            domainsQuery.refetch();
            aggregateQuery.refetch();
            forensicQuery.refetch();
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
              onChange={(event) =>
                setDraftState((current) => ({
                  ...current,
                  reportType: event.target.value === "forensic" ? "forensic" : "aggregate",
                  page: 1,
                  includeSpf: event.target.value === "forensic" ? "" : current.includeSpf,
                  includeDkim: event.target.value === "forensic" ? "" : current.includeDkim,
                  includeDisposition: event.target.value === "forensic" ? "" : current.includeDisposition,
                  excludeSpf: event.target.value === "forensic" ? "" : current.excludeSpf,
                  excludeDkim: event.target.value === "forensic" ? "" : current.excludeDkim,
                  excludeDisposition: event.target.value === "forensic" ? "" : current.excludeDisposition,
                }))
              }
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
              onChange={(event) => setDraftState((current) => ({ ...current, query: event.target.value }))}
              placeholder={draftState.reportType === "forensic" ? "Not available for forensic reports" : "IP, org, host, or address"}
              value={draftState.query}
            />
          </label>
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
          <div className="search-toolbar-actions">
            <button className="button-secondary" onClick={() => setIsFiltersOpen(true)} type="button">
              More filters
            </button>
            <button className="button-primary" type="submit">
              Search
            </button>
            <button className="button-secondary" onClick={resetSearch} type="button">
              Reset
            </button>
          </div>
        </form>
        <div className="search-toolbar-meta">
          <span className="status-text">{getDomainSummaryLabel(draftState.domains.length, domains.length)}</span>
          {draftState.reportType === "forensic" ? (
            <span className="status-text">Forensic reports use domain and date filters only.</span>
          ) : null}
        </div>
      </section>

      <section className="surface-card stack">
        <div className="section-heading">
          <div className="stack" style={{ gap: 8 }}>
            <h2 className="section-title">{currentState.reportType === "aggregate" ? "Results" : "Forensic reports"}</h2>
            <p className="section-intro">{resultsSummary}</p>
          </div>
          {hasAppliedFilters ? (
            <button className="button-secondary" onClick={resetSearch} type="button">
              Clear all
            </button>
          ) : null}
        </div>
        {hasAppliedFilters ? (
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
        {isLoading ? <p className="status-text">Loading results...</p> : null}
        {error ? <p className="error-text">{error instanceof Error ? error.message : "Failed to load results"}</p> : null}
        {domainsQuery.error ? (
          <p className="error-text">
            {domainsQuery.error instanceof Error ? domainsQuery.error.message : "Failed to load visible domains"}
          </p>
        ) : null}
        {aggregateResult && currentState.reportType === "aggregate" ? (
          <AggregateSearchResultsTable
            emptyMessage="No aggregate results found."
            onQuickFilter={handleQuickFilter}
            onViewReport={setSelectedAggregateReportId}
            result={aggregateResult}
          />
        ) : null}
        {forensicResult && currentState.reportType === "forensic" ? (
          <ForensicResultsTable
            emptyMessage="No forensic reports found."
            onQuickFilter={handleQuickFilter}
            onViewReport={setSelectedForensicReportId}
            result={forensicResult}
          />
        ) : null}
        {activeResult ? (
          <div className="pagination-row">
            <span className="status-text">
              Page {activeResult.page} of {totalPages}
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

      <SlideOverPanel
        description="Pick domains and, for aggregate searches, refine the pass/fail and disposition filters."
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
          <div className="stack" style={{ gap: 10 }}>
            <span className="field-label">Domains</span>
            {domainsQuery.isLoading ? <p className="status-text">Loading domains...</p> : null}
            {!domainsQuery.isLoading && !domains.length ? (
              <p className="status-text">No visible domains are available for this account yet.</p>
            ) : null}
            <div className="checkbox-grid">
              {domains.map((domain: DomainSummary) => (
                <label className="checkbox-card" key={domain.id}>
                  <input
                    checked={draftState.domains.includes(domain.name)}
                    onChange={() =>
                      setDraftState((current) => ({
                        ...current,
                        domains: toggleValue(current.domains, domain.name),
                      }))
                    }
                    type="checkbox"
                  />
                  <span>{domain.name}</span>
                </label>
              ))}
            </div>
          </div>

          {draftState.reportType === "aggregate" ? (
            <div className="search-state-grid">
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
          ) : null}

          <div className="dialog-actions">
            <button className="button-secondary" onClick={() => setIsFiltersOpen(false)} type="button">
              Close
            </button>
            <button className="button-primary" type="submit">
              Apply filters
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
      {selectedForensicReportId ? (
        <ReportDetailModal
          kind="forensic"
          onClose={() => setSelectedForensicReportId(null)}
          reportId={selectedForensicReportId}
        />
      ) : null}
    </AppShell>
  );
}
