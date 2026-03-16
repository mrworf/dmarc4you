"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api/client";
import type {
  AggregateReportDetailResponse,
  ForensicReportDetailResponse,
} from "@/lib/api/types";

type AggregateModalProps = {
  kind: "aggregate";
  reportId: string;
  onClose: () => void;
};

type ForensicModalProps = {
  kind: "forensic";
  reportId: string;
  onClose: () => void;
};

type ReportDetailModalProps = AggregateModalProps | ForensicModalProps;

export function ReportDetailModal(props: ReportDetailModalProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        props.onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [props]);

  const aggregateQuery = useQuery({
    queryKey: ["report-detail", "aggregate", props.reportId],
    queryFn: () => apiClient.get<AggregateReportDetailResponse>(`/api/v1/reports/aggregate/${props.reportId}`),
    enabled: props.kind === "aggregate",
  });

  const forensicQuery = useQuery({
    queryKey: ["report-detail", "forensic", props.reportId],
    queryFn: () => apiClient.get<ForensicReportDetailResponse>(`/api/v1/reports/forensic/${props.reportId}`),
    enabled: props.kind === "forensic",
  });

  const isLoading = props.kind === "aggregate" ? aggregateQuery.isLoading : forensicQuery.isLoading;
  const error = props.kind === "aggregate" ? aggregateQuery.error : forensicQuery.error;
  const aggregate = props.kind === "aggregate" ? aggregateQuery.data : null;
  const forensic = props.kind === "forensic" ? forensicQuery.data : null;

  return (
    <div className="modal-backdrop" onClick={props.onClose} role="presentation">
      <section
        aria-modal="true"
        className="modal-card"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="modal-header">
          <div>
            <p className="eyebrow">Report detail</p>
            <h2 style={{ margin: 0 }}>
              {props.kind === "aggregate" ? "Aggregate report" : "Forensic report"}
            </h2>
          </div>
          <button className="button-secondary" onClick={props.onClose} type="button">
            Close
          </button>
        </div>

        {isLoading ? <p className="status-text">Loading report detail...</p> : null}
        {error ? <p className="error-text">{error instanceof Error ? error.message : "Failed to load report detail"}</p> : null}

        {aggregate ? (
          <div className="stack">
            <div className="detail-grid">
              <article className="detail-card">
                <span className="stat-label">Domain</span>
                <strong>{aggregate.domain}</strong>
              </article>
              <article className="detail-card">
                <span className="stat-label">Org</span>
                <strong>{aggregate.org_name ?? "n/a"}</strong>
              </article>
              <article className="detail-card">
                <span className="stat-label">Report ID</span>
                <strong>{aggregate.report_id}</strong>
              </article>
              <article className="detail-card">
                <span className="stat-label">Records</span>
                <strong>{aggregate.records.length}</strong>
              </article>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Source IP</th>
                    <th>Resolved name</th>
                    <th>Resolved domain</th>
                    <th>Count</th>
                    <th>Disposition</th>
                    <th>DKIM</th>
                    <th>SPF</th>
                    <th>Header from</th>
                  </tr>
                </thead>
                <tbody>
                  {aggregate.records.map((record) => (
                    <tr key={record.id}>
                      <td>{record.source_ip ?? "n/a"}</td>
                      <td>{record.resolved_name ?? "n/a"}</td>
                      <td>{record.resolved_name_domain ?? "n/a"}</td>
                      <td>{record.count}</td>
                      <td>{record.disposition ?? "n/a"}</td>
                      <td>{record.dkim_result ?? "n/a"}</td>
                      <td>{record.spf_result ?? "n/a"}</td>
                      <td>{record.header_from ?? "n/a"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {forensic ? (
          <div className="detail-grid">
            <article className="detail-card">
              <span className="stat-label">Domain</span>
              <strong>{forensic.domain}</strong>
            </article>
            <article className="detail-card">
              <span className="stat-label">Source IP</span>
              <strong>{forensic.source_ip ?? "n/a"}</strong>
            </article>
            <article className="detail-card">
              <span className="stat-label">Header from</span>
              <strong>{forensic.header_from ?? "n/a"}</strong>
            </article>
            <article className="detail-card">
              <span className="stat-label">Failure</span>
              <strong>{forensic.failure_type ?? "n/a"}</strong>
            </article>
            <article className="detail-card">
              <span className="stat-label">SPF</span>
              <strong>{forensic.spf_result ?? "n/a"}</strong>
            </article>
            <article className="detail-card">
              <span className="stat-label">DKIM</span>
              <strong>{forensic.dkim_result ?? "n/a"}</strong>
            </article>
            <article className="detail-card">
              <span className="stat-label">DMARC</span>
              <strong>{forensic.dmarc_result ?? "n/a"}</strong>
            </article>
            <article className="detail-card">
              <span className="stat-label">Arrival</span>
              <strong>{forensic.arrival_time ?? "n/a"}</strong>
            </article>
            <article className="detail-card detail-card-wide">
              <span className="stat-label">Resolved host</span>
              <strong>{forensic.resolved_name ?? "n/a"}</strong>
              <span className="status-text">{forensic.resolved_name_domain ?? "n/a"}</span>
            </article>
            <article className="detail-card detail-card-wide">
              <span className="stat-label">Envelope</span>
              <strong>{forensic.envelope_from ?? "n/a"}</strong>
              <span className="status-text">{forensic.envelope_to ?? "n/a"}</span>
            </article>
          </div>
        ) : null}
      </section>
    </div>
  );
}
