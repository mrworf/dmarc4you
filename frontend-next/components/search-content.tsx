"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { ReportDetailModal } from "@/components/report-detail-modal";
import { AggregateSearchResultsTable, ForensicResultsTable } from "@/components/search-results-table";
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

export function SearchContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const currentState = useMemo(() => parseSearchState(searchParams), [searchParams]);
  const [draftState, setDraftState] = useState<SearchState>(currentState);
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

  function updateUrl(state: SearchState) {
    const nextParams = buildSearchRouteParams(state);
    router.replace(nextParams ? `${pathname}?${nextParams}` : pathname);
  }

  function applySearch() {
    updateUrl({ ...draftState, page: 1 });
  }

  function resetSearch() {
    const resetState: SearchState = {
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
    setDraftState(resetState);
    updateUrl(resetState);
  }

  function goToPage(page: number) {
    updateUrl({ ...currentState, page });
  }

  const domains = domainsQuery.data?.domains ?? [];

  return (
    <AppShell
      title="Search"
      description="Search aggregate and forensic reports across the domains you can access."
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
      <section className="panel-grid">
        <article className="stat-card">
          <p className="stat-label">Report type</p>
          <p className="stat-value">{currentState.reportType === "aggregate" ? "Aggregate" : "Forensic"}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Selected domains</p>
          <p className="stat-value">{currentState.domains.length}</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Backend total</p>
          <p className="stat-value">{activeResult?.total ?? 0}</p>
        </article>
      </section>

      <section className="surface-card stack">
        <div>
          <p className="eyebrow">Filters</p>
          <h2 style={{ margin: "0 0 8px" }}>Search reports</h2>
          <p className="status-text">Choose report type, date range, domains, and result filters to narrow the list.</p>
        </div>

        <div className="search-state-grid">
          <label className="field-label">
            Report type
            <select
              className="field-input"
              onChange={(event) =>
                setDraftState((current) => ({
                  ...current,
                  reportType: event.target.value === "forensic" ? "forensic" : "aggregate",
                  page: 1,
                }))
              }
              value={draftState.reportType}
            >
              <option value="aggregate">Aggregate</option>
              <option value="forensic">Forensic</option>
            </select>
          </label>
          <label className="field-label">
            Free-text query
            <input
              className="field-input"
              disabled={draftState.reportType === "forensic"}
              onChange={(event) => setDraftState((current) => ({ ...current, query: event.target.value }))}
              placeholder={draftState.reportType === "forensic" ? "Aggregate only" : "Google, 192.0.2, example"}
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
        </div>

        <div className="stack" style={{ gap: 10 }}>
          <span className="field-label">Domains</span>
          {domainsQuery.isLoading ? <p className="status-text">Loading domains...</p> : null}
          {domainsQuery.error ? (
            <p className="error-text">
              {domainsQuery.error instanceof Error ? domainsQuery.error.message : "Failed to load domains"}
            </p>
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
        ) : (
          <p className="status-text">Forensic mode focuses on message-level results, so some aggregate-only filters are unavailable.</p>
        )}

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <button className="button-primary" onClick={applySearch} type="button">
            Search
          </button>
          <button className="button-secondary" onClick={resetSearch} type="button">
            Reset
          </button>
        </div>
      </section>

      <section className="surface-card stack">
        <div>
          <p className="eyebrow">Results</p>
          <h2 style={{ margin: "0 0 8px" }}>
            {currentState.reportType === "aggregate" ? "Aggregate results" : "Forensic reports"}
          </h2>
          <p className="status-text">Filters and pagination stay in the URL so you can refresh or share the current view.</p>
        </div>
        {isLoading ? <p className="status-text">Loading results...</p> : null}
        {error ? <p className="error-text">{error instanceof Error ? error.message : "Failed to load results"}</p> : null}
        {aggregateResult && currentState.reportType === "aggregate" ? (
          <AggregateSearchResultsTable
            emptyMessage="No aggregate results found."
            onViewReport={setSelectedAggregateReportId}
            result={aggregateResult}
          />
        ) : null}
        {forensicResult && currentState.reportType === "forensic" ? (
          <ForensicResultsTable
            emptyMessage="No forensic reports found."
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
