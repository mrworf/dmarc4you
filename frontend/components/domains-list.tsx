import type { DomainSummary } from "@/lib/api/types";

export function DomainsList({ domains }: { domains: DomainSummary[] }) {
  if (!domains.length) {
    return <p className="status-text">No domains are visible for this account yet.</p>;
  }

  return (
    <div className="domain-list">
      {domains.map((domain) => (
        <article className="domain-row" key={domain.id}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
            <strong>{domain.name}</strong>
            <span className="pill">{domain.status}</span>
          </div>
          <div className="domain-meta">
            <span>ID {domain.id}</span>
            <span>Created {new Date(domain.created_at).toLocaleString()}</span>
            {domain.retention_days ? <span>Retention {domain.retention_days}d</span> : null}
            {domain.retention_paused ? <span>Retention paused</span> : null}
          </div>
        </article>
      ))}
    </div>
  );
}
