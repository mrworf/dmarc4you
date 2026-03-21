import { Fragment, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

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
import { renderCountryLabel } from "@/lib/country-display";

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
    | "exclude_dmarc_alignment"
    | "country";
};

type QuickFilterActions = {
  includeAction?: SearchQuickFilterOption;
  excludeAction?: SearchQuickFilterOption;
};

type BranchState = {
  contextKey?: string;
  data?: GroupedSearchResponse;
  error?: string;
  isLoading: boolean;
  path: GroupPathPart[];
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

function isSamePath(left: GroupPathPart[], right: GroupPathPart[]): boolean {
  return left.length === right.length && left.every((part, index) => part.field === right[index]?.field && part.value === right[index]?.value);
}

function isPathDescendant(path: GroupPathPart[], ancestor: GroupPathPart[]): boolean {
  return path.length > ancestor.length && ancestor.every((part, index) => part.field === path[index]?.field && part.value === path[index]?.value);
}

function isPathPrefixCompatible(path: GroupPathPart[], grouping: string[]): boolean {
  return path.length <= grouping.length && path.every((part, index) => grouping[index] === part.field);
}

function hasRootNode(items: Array<GroupedSearchNode | GroupedSearchLeafRow>, path: GroupPathPart[]): boolean {
  if (!path.length) {
    return true;
  }
  const rootKey = pathKey(path.slice(0, 1));
  return items.some((item) => isGroupedNode(item) && pathKey(item.path) === rootKey);
}

function pruneExpandedPaths(
  expandedPaths: Record<string, GroupPathPart[]>,
  initialResult: GroupedSearchResponse,
  grouping: string[],
): Record<string, GroupPathPart[]> {
  return Object.fromEntries(
    Object.entries(expandedPaths).filter(([, path]) => isPathPrefixCompatible(path, grouping) && hasRootNode(initialResult.items, path)),
  );
}

function pruneBranchCache(
  branches: Record<string, BranchState>,
  initialResult: GroupedSearchResponse,
  grouping: string[],
): Record<string, BranchState> {
  return Object.fromEntries(
    Object.entries(branches).filter(([, branch]) => isPathPrefixCompatible(branch.path, grouping) && hasRootNode(initialResult.items, branch.path)),
  );
}

function reconcileExpandedPathsForBranch(
  expandedPaths: Record<string, GroupPathPart[]>,
  path: GroupPathPart[],
  data: GroupedSearchResponse,
): Record<string, GroupPathPart[]> {
  return Object.fromEntries(
    Object.entries(expandedPaths).filter(([, candidatePath]) => {
      if (isSamePath(candidatePath, path) || !isPathDescendant(candidatePath, path)) {
        return true;
      }
      if (data.level_kind !== "group") {
        return false;
      }
      const nextChildPath = candidatePath.slice(0, path.length + 1);
      return data.items.some((item) => isGroupedNode(item) && isSamePath(item.path, nextChildPath));
    }),
  );
}

function pruneBranchesForExpandedPaths(
  branches: Record<string, BranchState>,
  expandedPaths: Record<string, GroupPathPart[]>,
): Record<string, BranchState> {
  return Object.fromEntries(
    Object.entries(branches).filter(([, branch]) =>
      Object.values(expandedPaths).some((path) => isSamePath(path, branch.path) || isPathDescendant(path, branch.path)),
    ),
  );
}

function CellValueWithActions({
  actions,
  textValue,
  value,
  onQuickFilter,
}: {
  textValue?: string;
  value: ReactNode;
  actions: QuickFilterActions;
  onQuickFilter?: (option: SearchQuickFilterOption) => void;
}) {
  const includeAction = actions.includeAction;
  const excludeAction = actions.excludeAction;
  const actionLabel = textValue ?? (typeof value === "string" ? value : "value");

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
          aria-label={`Exclude ${actionLabel}`}
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

function getStatusQuickFilterActions(column: string, value: string): QuickFilterActions {
  if (!value) {
    return {};
  }
  switch (column) {
    case "disposition":
      return {
        includeAction: { label: "Include disposition", target: "include_disposition", value },
        excludeAction: { label: "Exclude disposition", target: "exclude_disposition", value },
      };
    case "dkim_result":
      return {
        includeAction: { label: "Include DKIM", target: "include_dkim", value },
        excludeAction: { label: "Exclude DKIM", target: "exclude_dkim", value },
      };
    case "spf_result":
      return {
        includeAction: { label: "Include SPF", target: "include_spf", value },
        excludeAction: { label: "Exclude SPF", target: "exclude_spf", value },
      };
    case "dmarc_alignment":
      return {
        includeAction: { label: "Include DMARC alignment", target: "include_dmarc_alignment", value },
        excludeAction: { label: "Exclude DMARC alignment", target: "exclude_dmarc_alignment", value },
      };
    case "dkim_alignment":
      return {
        includeAction: { label: "Include DKIM alignment", target: "include_dkim_alignment", value },
        excludeAction: { label: "Exclude DKIM alignment", target: "exclude_dkim_alignment", value },
      };
    case "spf_alignment":
      return {
        includeAction: { label: "Include SPF alignment", target: "include_spf_alignment", value },
        excludeAction: { label: "Exclude SPF alignment", target: "exclude_spf_alignment", value },
      };
    default:
      return {};
  }
}

function renderStatusPillCell(
  column: string,
  itemValue: string | null,
  tone: string,
  onQuickFilter?: (option: SearchQuickFilterOption) => void,
) {
  if (!itemValue) {
    return "n/a";
  }
  return (
    <CellValueWithActions
      actions={getStatusQuickFilterActions(column, itemValue)}
      onQuickFilter={onQuickFilter}
      textValue={itemValue}
      value={<StatusPill tone={tone} value={itemValue} />}
    />
  );
}

function SummaryBar({
  segments,
  showCountLabel = true,
  title,
}: {
  showCountLabel?: boolean;
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
      {showCountLabel ? <span className="summary-bar-count">{total}</span> : null}
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
      return item.disposition ? getStatusQuickFilterActions(column, item.disposition) : {};
    case "dkim_result":
      return item.dkim_result ? getStatusQuickFilterActions(column, item.dkim_result) : {};
    case "spf_result":
      return item.spf_result ? getStatusQuickFilterActions(column, item.spf_result) : {};
    case "dmarc_alignment":
      return item.dmarc_alignment ? getStatusQuickFilterActions(column, item.dmarc_alignment) : {};
    case "dkim_alignment":
      return item.dkim_alignment ? getStatusQuickFilterActions(column, item.dkim_alignment) : {};
    case "spf_alignment":
      return item.spf_alignment ? getStatusQuickFilterActions(column, item.spf_alignment) : {};
    case "domain":
      return item.domain ? { includeAction: { label: "Limit to domain", target: "domains", value: item.domain } } : {};
    case "org_name":
      return item.org_name ? { includeAction: { label: "Include in search", target: "query", value: item.org_name } } : {};
    case "country_code":
    case "country_name":
      return item.country_name
        ? { includeAction: { label: "Filter by country", target: "country", value: item.country_name } }
        : {};
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
  contextKey,
  emptyMessage,
  grouping,
  initialResult,
  loadBranch,
  onQuickFilter,
  onViewReport,
  showPeriodColumn = true,
  showSummaryCounts = true,
  visibleColumns,
}: {
  contextKey: string;
  emptyMessage: string;
  grouping: string[];
  initialResult: GroupedSearchResponse;
  loadBranch: (path: GroupPathPart[]) => Promise<GroupedSearchResponse>;
  onQuickFilter?: (option: SearchQuickFilterOption) => void;
  onViewReport?: (reportId: string) => void;
  showPeriodColumn?: boolean;
  showSummaryCounts?: boolean;
  visibleColumns?: string[];
}) {
  const [expandedPaths, setExpandedPaths] = useState<Record<string, GroupPathPart[]>>({});
  const [branches, setBranches] = useState<Record<string, BranchState>>({});
  const contextKeyRef = useRef(contextKey);
  const loadBranchRef = useRef(loadBranch);

  useEffect(() => {
    contextKeyRef.current = contextKey;
  }, [contextKey]);

  useEffect(() => {
    loadBranchRef.current = loadBranch;
  }, [loadBranch]);

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
  const groupedColumnCount = showPeriodColumn ? 7 : 6;

  const collapsePath = useCallback((path: GroupPathPart[]) => {
    setExpandedPaths((current) =>
      Object.fromEntries(
        Object.entries(current).filter(([, candidatePath]) => !isSamePath(candidatePath, path) && !isPathDescendant(candidatePath, path)),
      ),
    );
    setBranches((current) =>
      Object.fromEntries(
        Object.entries(current).filter(([, branch]) => !isSamePath(branch.path, path) && !isPathDescendant(branch.path, path)),
      ),
    );
  }, []);

  const refreshBranch = useCallback(
    async (path: GroupPathPart[]) => {
      const key = pathKey(path);
      const requestContextKey = contextKeyRef.current;

      setBranches((current) => {
        const branch = current[key];
        if (branch?.isLoading && branch.contextKey === requestContextKey) {
          return current;
        }
        return {
          ...current,
          [key]: {
            contextKey: requestContextKey,
            data: branch?.data,
            error: undefined,
            isLoading: true,
            path,
          },
        };
      });

      try {
        const data = await loadBranchRef.current(path);
        if (contextKeyRef.current !== requestContextKey) {
          return;
        }
        if (!data.items.length && data.total === 0) {
          collapsePath(path);
          return;
        }

        setBranches((current) => ({
          ...current,
          [key]: {
            contextKey: requestContextKey,
            data,
            error: undefined,
            isLoading: false,
            path,
          },
        }));
        setExpandedPaths((current) => {
          const nextExpandedPaths = reconcileExpandedPathsForBranch(current, path, data);
          setBranches((branchState) => pruneBranchesForExpandedPaths(branchState, nextExpandedPaths));
          return nextExpandedPaths;
        });
      } catch (error) {
        if (contextKeyRef.current !== requestContextKey) {
          return;
        }
        setBranches((current) => ({
          ...current,
          [key]: {
            contextKey: requestContextKey,
            data: current[key]?.data,
            error: error instanceof Error ? error.message : "Failed to load grouped results",
            isLoading: false,
            path,
          },
        }));
      }
    },
    [collapsePath],
  );

  async function toggleBranch(node: GroupedSearchNode) {
    const key = pathKey(node.path);
    const isExpanded = !!expandedPaths[key];
    if (isExpanded) {
      setExpandedPaths((current) =>
        Object.fromEntries(
          Object.entries(current).filter(([, path]) => !isSamePath(path, node.path) && !isPathDescendant(path, node.path)),
        ),
      );
      return;
    }
    setExpandedPaths((current) => ({ ...current, [key]: node.path }));
    if (branches[key]?.data && branches[key]?.contextKey === contextKey && !branches[key]?.isLoading) {
      return;
    }
    void refreshBranch(node.path);
  }

  useEffect(() => {
    const nextExpandedPaths = pruneExpandedPaths(expandedPaths, initialResult, grouping);
    if (
      Object.keys(nextExpandedPaths).length !== Object.keys(expandedPaths).length ||
      Object.keys(nextExpandedPaths).some((key) => !expandedPaths[key] || !isSamePath(nextExpandedPaths[key], expandedPaths[key]))
    ) {
      setExpandedPaths(nextExpandedPaths);
    }

    const nextBranches = pruneBranchCache(branches, initialResult, grouping);
    if (
      Object.keys(nextBranches).length !== Object.keys(branches).length ||
      Object.keys(nextBranches).some((key) => nextBranches[key] !== branches[key])
    ) {
      setBranches(nextBranches);
    }

    Object.values(nextExpandedPaths).forEach((path) => {
      const key = pathKey(path);
      const branch = nextBranches[key];
      if (!branch || branch.contextKey !== contextKey) {
        void refreshBranch(path);
      }
    });
  }, [branches, contextKey, expandedPaths, grouping, initialResult, refreshBranch]);

  function renderBranchRows(items: Array<GroupedSearchNode | GroupedSearchLeafRow>, depth: number): JSX.Element[] {
    const rows: JSX.Element[] = [];
    for (const item of items) {
      if (!isGroupedNode(item)) {
        continue;
      }

      const key = pathKey(item.path);
      const branch = branches[key];
      const isExpanded = !!expandedPaths[key];
      rows.push(
        <Fragment key={`group-${key}`}>
          <tr className="group-row" data-group-key={key}>
            <td>
              <div className="group-cell" style={{ paddingLeft: depth * 18 }}>
                <button
                  aria-expanded={isExpanded}
                  aria-label={`${isExpanded ? "Collapse" : "Expand"} ${getAggregateFieldLabel(item.field)} ${item.label}`}
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
                showCountLabel={showSummaryCounts}
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
                showCountLabel={showSummaryCounts}
                title="Policy"
              />
            </td>
            {showPeriodColumn ? (
              <td>
                {item.first_record_date ?? "n/a"}
                {item.last_record_date && item.last_record_date !== item.first_record_date ? ` to ${item.last_record_date}` : ""}
              </td>
            ) : null}
          </tr>
          {isExpanded && branch?.isLoading ? (
            <tr>
              <td className="status-text" colSpan={groupedColumnCount}>
                {branch.data ? "Updating grouped results..." : "Loading grouped results..."}
              </td>
            </tr>
          ) : null}
          {isExpanded && branch?.error ? (
            <tr>
              <td className="error-text" colSpan={groupedColumnCount}>
                {branch.error}
              </td>
            </tr>
          ) : null}
          {isExpanded && branch?.data && branch.data.level_kind === "group" ? renderBranchRows(branch.data.items, depth + 1) : null}
          {isExpanded && branch?.data && branch.data.level_kind === "row" ? (
            <tr>
              <td colSpan={groupedColumnCount}>
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
            {showPeriodColumn ? <th>Period</th> : null}
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
      return (
        <CellValueWithActions
          actions={getAggregateQuickFilterActions(column, item)}
          onQuickFilter={onQuickFilter}
          textValue={item.country_name ?? item.country_code ?? undefined}
          value={renderCountryLabel(item.country_code, item.country_name)}
        />
      );
    case "country_name":
      return (
        <CellValueWithActions
          actions={getAggregateQuickFilterActions(column, item)}
          onQuickFilter={onQuickFilter}
          textValue={item.country_name ?? undefined}
          value={renderCountryLabel(item.country_code, item.country_name)}
        />
      );
    case "count":
      return item.count;
    case "disposition":
      return renderStatusPillCell(column, item.disposition, `disposition-${item.disposition ?? ""}`, onQuickFilter);
    case "dkim_result":
      return renderStatusPillCell(column, item.dkim_result, `result-${item.dkim_result ?? ""}`, onQuickFilter);
    case "spf_result":
      return renderStatusPillCell(column, item.spf_result, `result-${item.spf_result ?? ""}`, onQuickFilter);
    case "dmarc_alignment":
      return renderStatusPillCell(column, item.dmarc_alignment, `dmarc-${item.dmarc_alignment ?? ""}`, onQuickFilter);
    case "dkim_alignment":
      return renderStatusPillCell(column, item.dkim_alignment, `alignment-${item.dkim_alignment ?? ""}`, onQuickFilter);
    case "spf_alignment":
      return renderStatusPillCell(column, item.spf_alignment, `alignment-${item.spf_alignment ?? ""}`, onQuickFilter);
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
              <td>{renderCountryLabel(item.country_code, item.country_name)}</td>
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
