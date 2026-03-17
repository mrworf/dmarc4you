import type {
  AggregateSearchResult,
  ForensicReportSummary,
  ForensicReportsResponse,
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
    | "exclude_disposition";
};

function isGroupedResult(item: AggregateSearchResult | GroupedSearchResult): item is GroupedSearchResult {
  return "group_label" in item;
}

function CellValueWithActions({
  actions,
  value,
  onQuickFilter,
}: {
  value: string;
  actions: SearchQuickFilterOption[];
  onQuickFilter?: (option: SearchQuickFilterOption) => void;
}) {
  if (!actions.length || !onQuickFilter) {
    return value;
  }

  return (
    <div className="cell-value-wrap">
      <span>{value}</span>
      <details className="cell-action-menu">
        <summary aria-label={`Filter by ${value}`} className="cell-action-trigger">
          +
        </summary>
        <div className="cell-action-list">
          {actions.map((action) => (
            <button
              className="button-link cell-action-item"
              key={`${action.target}:${action.value}`}
              onClick={(event) => {
                event.preventDefault();
                onQuickFilter(action);
                event.currentTarget.closest("details")?.removeAttribute("open");
              }}
              type="button"
            >
              {action.label}
            </button>
          ))}
        </div>
      </details>
    </div>
  );
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
              if (!isGroupedResult(item)) {
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
    : ["record_date", "source_ip", "resolved_name", "count", "disposition", "dkim_result", "spf_result", "domain", "org_name"];

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
            if (isGroupedResult(item)) {
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

function renderAggregateCell(
  column: string,
  item: AggregateSearchResult,
  onQuickFilter?: (option: SearchQuickFilterOption) => void,
) {
  switch (column) {
    case "record_date":
      return item.record_date ?? "n/a";
    case "source_ip":
      return (
        <CellValueWithActions
          actions={item.source_ip ? [{ label: "Include in search", target: "query", value: item.source_ip }] : []}
          onQuickFilter={onQuickFilter}
          value={item.source_ip ?? "n/a"}
        />
      );
    case "resolved_name":
      return (
        <CellValueWithActions
          actions={item.resolved_name ? [{ label: "Include in search", target: "query", value: item.resolved_name }] : []}
          onQuickFilter={onQuickFilter}
          value={item.resolved_name ?? "n/a"}
        />
      );
    case "resolved_name_domain":
      if (!item.resolved_name_domain || item.resolved_name_domain === item.resolved_name) {
        return "n/a";
      }
      return (
        <CellValueWithActions
          actions={
            item.resolved_name_domain ? [{ label: "Include in search", target: "query", value: item.resolved_name_domain }] : []
          }
          onQuickFilter={onQuickFilter}
          value={item.resolved_name_domain ?? "n/a"}
        />
      );
    case "country_code":
      return item.country_code ?? "n/a";
    case "country_name":
      return item.country_name ?? "n/a";
    case "count":
      return item.count;
    case "disposition":
      return (
        <CellValueWithActions
          actions={
            item.disposition
              ? [
                  { label: "Include disposition", target: "include_disposition", value: item.disposition },
                  { label: "Exclude disposition", target: "exclude_disposition", value: item.disposition },
                ]
              : []
          }
          onQuickFilter={onQuickFilter}
          value={item.disposition ?? "n/a"}
        />
      );
    case "dkim_result":
      return (
        <CellValueWithActions
          actions={
            item.dkim_result
              ? [
                  { label: "Include DKIM", target: "include_dkim", value: item.dkim_result },
                  { label: "Exclude DKIM", target: "exclude_dkim", value: item.dkim_result },
                ]
              : []
          }
          onQuickFilter={onQuickFilter}
          value={item.dkim_result ?? "n/a"}
        />
      );
    case "spf_result":
      return (
        <CellValueWithActions
          actions={
            item.spf_result
              ? [
                  { label: "Include SPF", target: "include_spf", value: item.spf_result },
                  { label: "Exclude SPF", target: "exclude_spf", value: item.spf_result },
                ]
              : []
          }
          onQuickFilter={onQuickFilter}
          value={item.spf_result ?? "n/a"}
        />
      );
    case "domain":
      return (
        <CellValueWithActions
          actions={item.domain ? [{ label: "Limit to domain", target: "domains", value: item.domain }] : []}
          onQuickFilter={onQuickFilter}
          value={item.domain}
        />
      );
    case "org_name":
      return (
        <CellValueWithActions
          actions={item.org_name ? [{ label: "Include in search", target: "query", value: item.org_name }] : []}
          onQuickFilter={onQuickFilter}
          value={item.org_name ?? "n/a"}
        />
      );
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
                  actions={item.domain ? [{ label: "Limit to domain", target: "domains", value: item.domain }] : []}
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
