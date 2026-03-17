"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { apiClient } from "@/lib/api/client";
import type { AuditEventsResponse } from "@/lib/api/types";
import { buildSearchParams, parseIntegerParam, parseStringParam } from "@/lib/url-state";

type AuditState = {
  actionTypes: string[];
  from: string;
  to: string;
  actor: string;
  page: number;
};

const pageSize = 50;

function parseActionTypes(value: string | null): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseAuditState(searchParams: URLSearchParams): AuditState {
  const actionTypes = parseActionTypes(searchParams.get("action_types"));
  const legacyActionType = parseStringParam(searchParams.get("action_type"));
  return {
    actionTypes: actionTypes.length ? actionTypes : legacyActionType ? [legacyActionType] : [],
    from: parseStringParam(searchParams.get("from")),
    to: parseStringParam(searchParams.get("to")),
    actor: parseStringParam(searchParams.get("actor")),
    page: parseIntegerParam(searchParams.get("page"), 1),
  };
}

function buildAuditRouteParams(state: AuditState): string {
  return buildSearchParams({
    action_types: state.actionTypes.length ? state.actionTypes.join(",") : "",
    from: state.from,
    to: state.to,
    actor: state.actor,
    page: state.page > 1 ? String(state.page) : "",
  });
}

function buildAuditPath(state: AuditState): string {
  const params = buildSearchParams({
    limit: String(pageSize),
    offset: String((state.page - 1) * pageSize),
    action_types: state.actionTypes.length ? state.actionTypes.join(",") : "",
    from: state.from,
    to: state.to,
    actor: state.actor,
  });
  return params ? `/api/v1/audit?${params}` : "/api/v1/audit";
}

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

export function AuditContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const currentState = useMemo(() => parseAuditState(searchParams), [searchParams]);
  const [draftState, setDraftState] = useState<AuditState>(currentState);

  useEffect(() => {
    setDraftState(currentState);
  }, [currentState]);

  const auditPath = useMemo(() => buildAuditPath(currentState), [currentState]);
  const auditQuery = useQuery({
    queryKey: ["audit", auditPath],
    queryFn: () => apiClient.get<AuditEventsResponse>(auditPath),
  });

  const events = auditQuery.data?.events ?? [];
  const availableActionTypes = auditQuery.data?.available_action_types ?? [];
  const hasNextPage = events.length >= pageSize;
  const hasPreviousPage = currentState.page > 1;

  function updateUrl(state: AuditState) {
    const nextParams = buildAuditRouteParams(state);
    router.replace(nextParams ? `${pathname}?${nextParams}` : pathname);
  }

  function applyFilters() {
    updateUrl({ ...draftState, page: 1 });
  }

  function resetFilters() {
    const resetState: AuditState = {
      actionTypes: [],
      from: "",
      to: "",
      actor: "",
      page: 1,
    };
    setDraftState(resetState);
    updateUrl(resetState);
  }

  function goToPage(page: number) {
    updateUrl({ ...currentState, page });
  }

  return (
    <AppShell
      title="Audit"
      description="Review recent security-sensitive actions and narrow the list with filters."
      actions={
        <button className="button-secondary" onClick={() => auditQuery.refetch()} type="button">
          Refresh
        </button>
      }
    >
      <section className="surface-card stack">
        <div className="section-heading">
          <div className="stack" style={{ gap: 8 }}>
            <h2 className="section-title">Filters</h2>
            <p className="section-intro">Filter by action, time range, or actor to focus on the events you need.</p>
          </div>
        </div>
        <div className="stack" style={{ gap: 12 }}>
          <span className="field-label" style={{ gap: 0 }}>
            Action types
          </span>
          {auditQuery.isLoading && !availableActionTypes.length ? <p className="status-text">Loading action types...</p> : null}
          {!auditQuery.isLoading && !availableActionTypes.length ? (
            <p className="status-text">No audit action types are available yet.</p>
          ) : null}
          {availableActionTypes.length ? (
            <div className="multi-select-list">
              {availableActionTypes.map((actionType) => (
                <label className="checkbox-card" key={actionType}>
                  <input
                    checked={draftState.actionTypes.includes(actionType)}
                    onChange={() =>
                      setDraftState((state) => ({
                        ...state,
                        actionTypes: toggleValue(state.actionTypes, actionType),
                      }))
                    }
                    type="checkbox"
                  />
                  <span>{actionType}</span>
                </label>
              ))}
            </div>
          ) : null}
        </div>
        <div className="search-state-grid">
          <label className="field-label">
            From
            <input
              className="field-input"
              onChange={(event) => setDraftState((state) => ({ ...state, from: event.target.value }))}
              type="date"
              value={draftState.from}
            />
          </label>
          <label className="field-label">
            To
            <input
              className="field-input"
              onChange={(event) => setDraftState((state) => ({ ...state, to: event.target.value }))}
              type="date"
              value={draftState.to}
            />
          </label>
          <label className="field-label">
            Actor ID
            <input
              className="field-input"
              onChange={(event) => setDraftState((state) => ({ ...state, actor: event.target.value }))}
              placeholder="usr_xxx"
              value={draftState.actor}
            />
          </label>
        </div>
        {draftState.actionTypes.length ? (
          <div className="filter-chip-row">
            {draftState.actionTypes.map((actionType) => (
              <span className="filter-chip" key={actionType}>
                <span>{actionType}</span>
                <button
                  aria-label={`Remove ${actionType}`}
                  className="filter-chip-remove"
                  onClick={() =>
                    setDraftState((state) => ({
                      ...state,
                      actionTypes: state.actionTypes.filter((entry) => entry !== actionType),
                    }))
                  }
                  type="button"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}
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
        <div className="section-heading">
          <div className="stack" style={{ gap: 8 }}>
            <h2 className="section-title">Audit log</h2>
            <p className="section-intro">
              Showing {events.length} event{events.length === 1 ? "" : "s"} on page {currentState.page}.
            </p>
          </div>
        </div>

        {auditQuery.isLoading ? <p className="status-text">Loading audit events...</p> : null}
        {auditQuery.error ? (
          <p className="error-text">{auditQuery.error instanceof Error ? auditQuery.error.message : "Failed to load audit events"}</p>
        ) : null}

        {!auditQuery.isLoading && !auditQuery.error && !events.length ? (
          <p className="status-text">No audit events matched the current filters.</p>
        ) : null}

        {events.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Action</th>
                  <th>Outcome</th>
                  <th>Summary</th>
                  <th>Actor</th>
                  <th>Source IP</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td>{new Date(event.timestamp).toLocaleString()}</td>
                    <td>{event.action_type}</td>
                    <td>{event.outcome || "n/a"}</td>
                    <td>{event.summary || "n/a"}</td>
                    <td>{event.actor_user_id || event.actor_type || "n/a"}</td>
                    <td>{event.source_ip || "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        <div className="pagination-row">
          <span className="status-text">Page {currentState.page}</span>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button className="button-secondary" disabled={!hasPreviousPage} onClick={() => goToPage(currentState.page - 1)} type="button">
              Previous
            </button>
            <button className="button-secondary" disabled={!hasNextPage} onClick={() => goToPage(currentState.page + 1)} type="button">
              Next
            </button>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
