import Link from "next/link";

import type { DashboardSummary } from "@/lib/api/types";

export function DashboardList({ dashboards }: { dashboards: DashboardSummary[] }) {
  if (!dashboards.length) {
    return <p className="status-text">No dashboards yet. Use the action bar to create or import one.</p>;
  }

  return (
    <div className="domain-list">
      {dashboards.map((dashboard) => (
        <article className="domain-row" key={dashboard.id}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
            <Link className="inline-link" href={`/dashboards/${dashboard.id}`}>
              <strong>{dashboard.name}</strong>
            </Link>
            <span className="pill">{dashboard.domain_ids.length} domain{dashboard.domain_ids.length === 1 ? "" : "s"}</span>
          </div>
          {dashboard.description ? (
            <p className="status-text" style={{ margin: 0 }}>
              {dashboard.description}
            </p>
          ) : null}
          <div className="domain-meta">
            <span>ID {dashboard.id}</span>
            <span>Updated {new Date(dashboard.updated_at).toLocaleString()}</span>
            <span>Owner {dashboard.owner_user_id}</span>
          </div>
        </article>
      ))}
    </div>
  );
}
