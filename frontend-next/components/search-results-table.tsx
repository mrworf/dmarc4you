import { Fragment, useEffect, useMemo, useState } from "react";

import type {
  AggregateSearchResult,
  ForensicReportSummary,
  ForensicReportsResponse,
  GroupPathPart,
  GroupedSearchLeafRow,
  GroupedSearchNode,
  GroupedSearchResponse,
  GroupedSearchResult,
  SearchRecordsResponse,
} from "@/lib/api/types";
import { getAggregateFieldLabel } from "@/lib/aggregate-field-metadata";

export type SearchQuickFilterOption = {
  label: string;
  value: string;
  target:
    | "domains"
    | "query"
    | "include_spf"
    | "exclude_spf"
    | "include_dkim"
    | "exclude_dkim"
    | "include_disposition"
    | "exclude_disposition"
    | "include_dkim_alignment"
    | "exclude_dkim_alignment"
    | "include_spf_alignment"
    | "exclude_spf_alignment"
    | "include_dmarc_alignment"
    | "exclude_dmarc_alignment";
};

type QuickFilterActions = {
  includeAction?: SearchQuickFilterOption;
  excludeAction?: SearchQuickFilterOption;
};

type BranchState = {
  data?: GroupedSearchResponse;
  error?: string;
  isLoading: boolean;
};

function isLegacyGroupedResult(item: AggregateSearchResult | GroupedSearchResult): item is GroupedSearchResult {
  return "group_label" in item;
}

function isGroupedNode(item: GroupedSearchNode | GroupedSearchLeafRow): item is GroupedSearchNode {
  return item.type === "group";
}

function pathKey(path: GroupPathPart[]): string {
  return path.map((part) => `${part.field}:${part.value}`).join("|");
}

function CellValueWithActions({
  actions,
  value,
  onQuickFilter,
}: {
  value: string;
  actions: QuickFilterActions;
  onQuickFilter?: (option: SearchQuickFilterOption) => void;
}) {
  const includeAction = actions.includeAction;
  const excludeAction = actions.excludeAction;

  return (
    <div className="cell-value-wrap">
      {includeAction && onQuickFilter ? (
        <button
          className="button-link cell-primary-action"
          onClick={(event) => {
            event.preventDefault();
            onQuickFilter(includeAction);
          }}
          type="button"
        >
          {value}
        </button>
      ) : (
        <span>{value}</span>
      )}
      {excludeAction && onQuickFilter ? (
        <button
          aria-label={`Exclude ${value}`}
          className="cell-exclude-trigger"
          onClick={(event) => {
            event.preventDefault();
            onQuickFilter(excludeAction);
          }}
          type="button"
        >
          -
        </button>
      ) : null}
    </div>
  );
}

function StatusPill({ tone, value }: { value: string; tone: string }) {
  return <span className={`status-pill status-pill-${tone}`}>{value}</span>;
}

function SummaryBar({
  segments,
  title,
}: {
  title: string;
  segments: Array<{ colorClass: string; label: string; value: number }>;
}) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  return (
    <div className="summary-bar-wrap" title={segments.map((segment) => `${segment.label}: ${segment.value}`).join(" · ")}>
      <div className="summary-bar" aria-hidden="true">
        {segments.map((segment) => {
          const width = total ? `${(segment.value / total) * 100}%` : "0%";
          return <span className={`summary-bar-segment ${segment.colorClass}`} key={segment.label} style={{ width }} />;
        })}
      </div>
      <span className="summary-bar-label">{title}</span>
      <span className="summary-bar-count">{total}</span>
    </div>
  );
}

function getGroupQuickFilterActions(field: string, value: string): QuickFilterActions {
  if (!value) {
    return {};
  }
  if (field === "domain") {
    return {
      includeAction: { label: "Limit to domain", target: "domains", value },
    };
  }
  if (field === "disposition") {
    return {
      includeAction: { label: "Include disposition", target: "include_disposition", value },
      excludeAction: { label: "Exclude disposition", target: "exclude_disposition", value },
    };
  }
  if (field === "dmarc_alignment") {
    return {
      includeAction: { label: "Include DMARC alignment", target: "include_dmarc_alignment", value },
      excludeAction: { label: "Exclude DMARC alignment", target: "exclude_dmarc_alignment", value },
    };
  }
  if (field === "dkim_alignment") {
    return {
      includeAction: { label: "Include DKIM alignment", target: "include_dkim_alignment", value },
      excludeAction: { label: "Exclude DKIM alignment", target: "exclude_dkim_alignment", value },
    };
  }
  if (field === "spf_alignment") {
    return {
      includeAction: { label: "Include SPF alignment", target: "include_spf_alignment", value },
      excludeAction: { label: "Exclude SPF alignment", target: "exclude_spf_alignment", value },
    };
  }
  if (field === "source_ip" || field === "resolved_name_domain" || field === "org_name") {
    return {
      includeAction: { label: "Include in search", target: "query", value },
    };
  }
  return {};
}

function getAggregateQuickFilterActions(column: string, item: AggregateSearchResult): QuickFilterActions {
  switch (column) {
    case "source_ip":
      return item.source_ip ? { includeAction: { label: "Include in search", target: "query", value: item.source_ip } } : {};
    case "resolved_name":
      return item.resolved_name ? { includeAction: { label: "Include in search", target: "query", value: item.resolved_name } } : {};
    case "resolved_name_domain":
      return item.resolved_name_domain && item.resolved_name_domain !== item.resolved_name
        ? { includeAction: { label: "Include in search", target: "query", value: item.resolved_name_domain } }
        : {};
    case "disposition":
      return item.disposition
        ? {
            includeAction: { label: "Include disposition", target: "include_disposition", value: item.disposition },
            excludeAction: { label: "Exclude disposition", target: "exclude_disposition", value: item.disposition },
          }
        : {};
    case "dkim_result":
      return item.dkim_result
        ? {
            includeAction: { label: "Include DKIM", target: "include_dkim", value: item.dkim_result },
            excludeAction: { label: "Exclude DKIM", target: "exclude_dkim", value: item.dkim_result },
          }
        : {};
    case "spf_result":
      return item.spf_result
        ? {
            includeAction: { label: "Include SPF", target: "include_spf", value: item.spf_result },
            excludeAction: { label: "Exclude SPF", target: "exclude_spf", value: item.spf_result },
          }
        : {};
    case "dmarc_alignment":
      return item.dmarc_alignment
        ? {
            includeAction: { label: "Include DMARC alignment", target: "include_dmarc_alignment", value: item.dmarc_alignment },
            excludeAction: { label: "Exclude DMARC alignment", target: "exclude_dmarc_alignment", value: item.dmarc_alignment },
          }
        : {};
    case "dkim_alignment":
      return item.dkim_alignment
        ? {
            includeAction: { label: "Include DKIM alignment", target: "include_dkim_alignment", value: item.dkim_alignment },
            excludeAction: { label: "Exclude DKIM alignment", target: "exclude_dkim_alignment", value: item.dkim_alignment },
          }
        : {};
    case "spf_alignment":
      return item.spf_alignment
        ? {
            includeAction: { label: "Include SPF alignment", target: "include_spf_alignment", value: item.spf_alignment },
            excludeAction: { label: "Exclude SPF alignment", target: "exclude_spf_alignment", value: item.spf_alignment },
          }
        : {};
    case "domain":
      return item.domain ? { includeAction: { label: "Limit to domain", target: "domains", value: item.domain } } : {};
    case "org_name":
      return item.org_name ? { includeAction: { label: "Include in search", target: "query", value: item.org_name } } : {};
    default:
      return {};
  }
}

export function AggregateSearchResultsTable({
  emptyMessage,
  onViewReport,
  onQuickFilter,
  result,
  visibleColumns,
}: {
  emptyMessage: string;
  onViewReport?: (reportId: string) => void;
  onQuickFilter?: (option: SearchQuickFilterOption) => void;
  result: SearchRecordsResponse;
  visibleColumns?: string[];
}) {
  if (!result.items.length) {
    return <p className="status-text">{emptyMessage}</p>;
  }

  if (result.group_by) {
    return (
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Group</th>
              <th>Messages</th>
              <th>Rows</th>
              <th>Reports</th>
              <th>First record date</th>
            </tr>
          </thead>
          <tbody>
            {result.items.map((item) => {
              if (!isLegacyGroupedResult(item)) {
                return null;
              }
              return (
                <tr key={`${item.group_by}:${item.group_value}`}>
                  <td>{item.group_label}</td>
                  <td>{item.count}</td>
                  <td>{item.row_count}</td>
                  <td>{item.report_count}</td>
                  <td>{item.record_date ?? "n/a"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  const columns = visibleColumns?.length
    ? visibleColumns.filter((column) => column !== "resolved_name_domain")
    : [
        "record_date",
        "source_ip",
        "resolved_name",
        "count",
        "disposition",
        "dkim_result",
        "spf_result",
        "dmarc_alignment",
        "dkim_alignment",
        "spf_alignment",
        "domain",
        "org_name",
      ];

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{getAggregateFieldLabel(column)}</th>
            ))}
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {result.items.map((item) => {
            if (isLegacyGroupedResult(item)) {
              return null;
            }
            return (
              <tr key={item.id}>
                {columns.map((column) => (
                  <td key={column}>{renderAggregateCell(column, item, onQuickFilter)}</td>
                ))}
                <td>
                  {onViewReport ? (
                    <button className="button-link" onClick={() => onViewReport(item.aggregate_report_id)} type="button">
                      View
                    </button>
                  ) : (
                    "n/a"
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function GroupedAggregateResultsTable({
  emptyMessage,
  grouping,
  initialResult,
  loadBranch,
  onQuickFilter,
  onViewReport,
  visibleColumns,
}: {
  emptyMessage: string;
  grouping: string[];
  initialResult: GroupedSearchResponse;
  loadBranch: (path: GroupPathPart[]) => Promise<GroupedSearchResponse>;
  onQuickFilter?: (option: SearchQuickFilterOption) => void;
  onViewReport?: (reportId: string) => void;
  visibleColumns?: string[];
}) {
  const [expandedKeys, setExpandedKeys] = useState<Record<string, boolean>>({});
  const [branches, setBranches] = useState<Record<string, BranchState>>({});

  useEffect(() => {
    setExpandedKeys({});
    setBranches({});
  }, [initialResult, grouping]);

  const leafColumns = useMemo(() => {
    const baseColumns = visibleColumns?.length
      ? visibleColumns.filter((column) => column !== "resolved_name_domain")
      : [
          "record_date",
          "source_ip",
          "resolved_name",
          "count",
          "disposition",
          "dkim_result",
          "spf_result",
          "dmarc_alignment",
          "dkim_alignment",
          "spf_alignment",
          "domain",
          "org_name",
        ];
    return baseColumns.filter((column) => !grouping.includes(column));
  }, [grouping, visibleColumns]);

  async function toggleBranch(node: GroupedSearchNode) {
    const key = pathKey(node.path);
    const isExpanded = !!expandedKeys[key];
    if (isExpanded) {
      setExpandedKeys((current) => ({ ...current, [key]: false }));
      return;
    }
    setExpandedKeys((current) => ({ ...current, [key]: true }));
    if (branches[key]?.data || branches[key]?.isLoading) {
      return;
    }
    setBranches((current) => ({ ...current, [key]: { isLoading: true } }));
    try {
      const data = await loadBranch(node.path);
      setBranches((current) => ({ ...current, [key]: { data, isLoading: false } }));
    } catch (error) {
      setBranches((current) => ({
        ...current,
        [key]: { error: error instanceof Error ? error.message : "Failed to load grouped results", isLoading: false },
      }));
    }
  }

  function renderBranchRows(items: Array<GroupedSearchNode | GroupedSearchLeafRow>, depth: number): JSX.Element[] {
    const rows: JSX.Element[] = [];
    for (const item of items) {
      if (!isGroupedNode(item)) {
        continue;
      }

      const key = pathKey(item.path);
      const branch = branches[key];
      const isExpanded = !!expandedKeys[key];
      rows.push(
        <Fragment key={`group-${key}`}>
          <tr className="group-row">
            <td>
              <div className="group-cell" style={{ paddingLeft: depth * 18 }}>
                <button
                  aria-expanded={isExpanded}
                  className="group-toggle"
                  onClick={() => {
                    void toggleBranch(item);
                  }}
                  type="button"
                >
                  {isExpanded ? "▾" : "▸"}
                </button>
                <div className="group-copy">
                  <div className="group-kicker">{getAggregateFieldLabel(item.field)}</div>
                  <CellValueWithActions
                    actions={getGroupQuickFilterActions(item.field, item.value)}
                    onQuickFilter={onQuickFilter}
                    value={item.label}
                  />
                </div>
              </div>
            </td>
            <td>{item.message_count}</td>
            <td>{item.row_count}</td>
            <td>{item.report_count}</td>
            <td>
              <SummaryBar
                segments={[
                  { colorClass: "summary-green", label: "Pass", value: item.dmarc_alignment_summary.pass },
                  { colorClass: "summary-red", label: "Fail", value: item.dmarc_alignment_summary.fail },
                  { colorClass: "summary-blue", label: "Unknown", value: item.dmarc_alignment_summary.unknown },
                ]}
                title="DMARC"
              />
            </td>
            <td>
              <SummaryBar
                segments={[
                  { colorClass: "summary-blue", label: "None", value: item.disposition_summary.none },
                  { colorClass: "summary-amber", label: "Quarantine", value: item.disposition_summary.quarantine },
                  { colorClass: "summary-red", label: "Reject", value: item.disposition_summary.reject },
                ]}
                title="Policy"
              />
            </td>
            <td>
              {item.first_record_date ?? "n/a"}
              {item.last_record_date && item.last_record_date !== item.first_record_date ? ` to ${item.last_record_date}` : ""}
            </td>
          </tr>
          {isExpanded && branch?.isLoading ? (
            <tr>
              <td className="status-text" colSpan={7}>
                Loading grouped results...
              </td>
            </tr>
          ) : null}
          {isExpanded && branch?.error ? (
            <tr>
              <td className="error-text" colSpan={7}>
                {branch.error}
              </td>
            </tr>
          ) : null}
          {isExpanded && branch?.data && branch.data.level_kind === "group" ? renderBranchRows(branch.data.items, depth + 1) : null}
          {isExpanded && branch?.data && branch.data.level_kind === "row" ? (
            <tr>
              <td colSpan={7}>
                <div className="group-leaf-wrap" style={{ paddingLeft: (depth + 1) * 18 }}>
                  <AggregateSearchResultsTable
                    emptyMessage="No leaf rows."
                    onQuickFilter={onQuickFilter}
                    onViewReport={onViewReport}
                    result={{
                      items: branch.data.items.map((leaf) => {
                        const row = leaf as GroupedSearchLeafRow;
                        return {
                          aggregate_report_id: row.aggregate_report_id,
                          count: row.count,
                          country_code: row.country_code,
                          country_name: row.country_name,
                          date_begin: row.date_begin,
                          date_end: row.date_end,
                          disposition: row.disposition,
                          dkim_alignment: row.dkim_alignment,
                          dkim_result: row.dkim_result,
                          dmarc_alignment: row.dmarc_alignment,
                          domain: row.domain,
                          envelope_from: row.envelope_from,
                          envelope_to: row.envelope_to,
                          geo_provider: row.geo_provider,
                          header_from: row.header_from,
                          id: row.id,
                          org_name: row.org_name,
                          record_date: row.record_date,
                          report_id: row.report_id,
                          resolved_name: row.resolved_name,
                          resolved_name_domain: row.resolved_name_domain,
                          source_ip: row.source_ip,
                          spf_alignment: row.spf_alignment,
                          spf_result: row.spf_result,
                        } as AggregateSearchResult;
                      }),
                      total: branch.data.total,
                      page: branch.data.page,
                      page_size: branch.data.page_size,
                      group_by: null,
                    }}
                    visibleColumns={leafColumns}
                  />
                </div>
              </td>
            </tr>
          ) : null}
        </Fragment>,
      );
    }
    return rows;
  }

  if (!initialResult.items.length) {
    return <p className="status-text">{emptyMessage}</p>;
  }

  return (
    <div className="table-wrap">
      <table className="data-table grouped-data-table">
        <thead>
          <tr>
            <th>Group</th>
            <th>Messages</th>
            <th>Rows</th>
            <th>Reports</th>
            <th>DMARC alignment</th>
            <th>Disposition</th>
            <th>Period</th>
          </tr>
        </thead>
        <tbody>{renderBranchRows(initialResult.items, 0)}</tbody>
      </table>
    </div>
  );
}

function renderAggregateCell(
  column: string,
  item: AggregateSearchResult,
  onQuickFilter?: (option: SearchQuickFilterOption) => void,
) {
  switch (column) {
    case "record_date":
      return item.record_date ?? "n/a";
    case "source_ip":
      return <CellValueWithActions actions={getAggregateQuickFilterActions(column, item)} onQuickFilter={onQuickFilter} value={item.source_ip ?? "n/a"} />;
    case "resolved_name":
      return <CellValueWithActions actions={getAggregateQuickFilterActions(column, item)} onQuickFilter={onQuickFilter} value={item.resolved_name ?? "n/a"} />;
    case "resolved_name_domain":
      if (!item.resolved_name_domain || item.resolved_name_domain === item.resolved_name) {
        return "n/a";
      }
      return <CellValueWithActions actions={getAggregateQuickFilterActions(column, item)} onQuickFilter={onQuickFilter} value={item.resolved_name_domain ?? "n/a"} />;
    case "country_code":
      return item.country_code ?? "n/a";
    case "country_name":
      return item.country_name ?? "n/a";
    case "count":
      return item.count;
    case "disposition":
      return item.disposition ? <StatusPill tone={`disposition-${item.disposition}`} value={item.disposition} /> : "n/a";
    case "dkim_result":
      return item.dkim_result ? <StatusPill tone={`result-${item.dkim_result}`} value={item.dkim_result} /> : "n/a";
    case "spf_result":
      return item.spf_result ? <StatusPill tone={`result-${item.spf_result}`} value={item.spf_result} /> : "n/a";
    case "dmarc_alignment":
      return item.dmarc_alignment ? <StatusPill tone={`dmarc-${item.dmarc_alignment}`} value={item.dmarc_alignment} /> : "n/a";
    case "dkim_alignment":
      return item.dkim_alignment ? <StatusPill tone={`alignment-${item.dkim_alignment}`} value={item.dkim_alignment} /> : "n/a";
    case "spf_alignment":
      return item.spf_alignment ? <StatusPill tone={`alignment-${item.spf_alignment}`} value={item.spf_alignment} /> : "n/a";
    case "domain":
      return <CellValueWithActions actions={getAggregateQuickFilterActions(column, item)} onQuickFilter={onQuickFilter} value={item.domain} />;
    case "org_name":
      return <CellValueWithActions actions={getAggregateQuickFilterActions(column, item)} onQuickFilter={onQuickFilter} value={item.org_name ?? "n/a"} />;
    case "header_from":
      return item.header_from ?? "n/a";
    case "envelope_from":
      return item.envelope_from ?? "n/a";
    case "envelope_to":
      return item.envelope_to ?? "n/a";
    case "report_id":
      return item.report_id;
    default:
      return "n/a";
  }
}

export function ForensicResultsTable({
  emptyMessage,
  onViewReport,
  onQuickFilter,
  result,
}: {
  emptyMessage: string;
  onViewReport?: (reportId: string) => void;
  onQuickFilter?: (option: SearchQuickFilterOption) => void;
  result: ForensicReportsResponse;
}) {
  if (!result.items.length) {
    return <p className="status-text">{emptyMessage}</p>;
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Domain</th>
            <th>Source IP</th>
            <th>Resolved name</th>
            <th>Resolved domain</th>
            <th>Country</th>
            <th>Header from</th>
            <th>SPF</th>
            <th>DKIM</th>
            <th>DMARC</th>
            <th>Failure</th>
            <th>Arrival</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {result.items.map((item: ForensicReportSummary) => (
            <tr key={item.id}>
              <td>
                <CellValueWithActions
                  actions={item.domain ? { includeAction: { label: "Limit to domain", target: "domains", value: item.domain } } : {}}
                  onQuickFilter={onQuickFilter}
                  value={item.domain}
                />
              </td>
              <td>{item.source_ip ?? "n/a"}</td>
              <td>{item.resolved_name ?? "n/a"}</td>
              <td>{item.resolved_name_domain ?? "n/a"}</td>
              <td>{item.country_code ? `${item.country_code} ${item.country_name ?? ""}`.trim() : "n/a"}</td>
              <td>{item.header_from ?? "n/a"}</td>
              <td>{item.spf_result ?? "n/a"}</td>
              <td>{item.dkim_result ?? "n/a"}</td>
              <td>{item.dmarc_result ?? "n/a"}</td>
              <td>{item.failure_type ?? "n/a"}</td>
              <td>{item.arrival_time ?? "n/a"}</td>
              <td>
                {onViewReport ? (
                  <button className="button-link" onClick={() => onViewReport(item.id)} type="button">
                    View
                  </button>
                ) : (
                  "n/a"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
