import type {
  AggregateSearchResult,
  ForensicReportSummary,
  ForensicReportsResponse,
  GroupedSearchResult,
  SearchRecordsResponse,
} from "@/lib/api/types";

function isGroupedResult(item: AggregateSearchResult | GroupedSearchResult): item is GroupedSearchResult {
  return "group_label" in item;
}

export function AggregateSearchResultsTable({
  emptyMessage,
  onViewReport,
  result,
}: {
  emptyMessage: string;
  onViewReport?: (reportId: string) => void;
  result: SearchRecordsResponse;
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
              <th>Total count</th>
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

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Record date</th>
            <th>Source IP</th>
            <th>Resolved name</th>
            <th>Resolved domain</th>
            <th>Count</th>
            <th>Disposition</th>
            <th>DKIM</th>
            <th>SPF</th>
            <th>Domain</th>
            <th>Org</th>
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
                <td>{item.record_date ?? "n/a"}</td>
                <td>{item.source_ip ?? "n/a"}</td>
                <td>{item.resolved_name ?? "n/a"}</td>
                <td>{item.resolved_name_domain ?? "n/a"}</td>
                <td>{item.count}</td>
                <td>{item.disposition ?? "n/a"}</td>
                <td>{item.dkim_result ?? "n/a"}</td>
                <td>{item.spf_result ?? "n/a"}</td>
                <td>{item.domain}</td>
                <td>{item.org_name ?? "n/a"}</td>
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

export function ForensicResultsTable({
  emptyMessage,
  onViewReport,
  result,
}: {
  emptyMessage: string;
  onViewReport?: (reportId: string) => void;
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
              <td>{item.domain}</td>
              <td>{item.source_ip ?? "n/a"}</td>
              <td>{item.resolved_name ?? "n/a"}</td>
              <td>{item.resolved_name_domain ?? "n/a"}</td>
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
