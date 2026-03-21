import Link from "next/link";

import type { DashboardSummary } from "@/lib/api/types";

function renderDashboardOwner(dashboard: DashboardSummary) {
  const owner = dashboard.owner;
  if (!owner) {
    return "Unknown";
  }
  if (owner.full_name && owner.email) {
    return (
      <>
        <span>{owner.full_name}</span>
        {" · "}
        <a className="inline-link" href={`mailto:${owner.email}`}>
          {owner.email}
        </a>
      </>
    );
  }
  if (owner.email) {
    return (
      <a className="inline-link" href={`mailto:${owner.email}`}>
        {owner.email}
      </a>
    );
  }
  return owner.full_name || owner.username;
}

export function DashboardList({ dashboards }: { dashboards: DashboardSummary[] }) {
  if (!dashboards.length) {
    return <p className="status-text">No dashboards yet. Use the action bar to create or import one.</p>;
  }

  return (
    <div className="domain-list">
      {dashboards.map((dashboard) => (
        <article className="domain-row" key={dashboard.id}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
            <Link className="inline-link" href={`/dashboards/${dashboard.id}`}>
              <strong>{dashboard.name}</strong>
            </Link>
          </div>
          {dashboard.description ? (
            <p className="status-text" style={{ margin: 0 }}>
              {dashboard.description}
            </p>
          ) : null}
          <div className="domain-meta">
            <span>
              Owner {renderDashboardOwner(dashboard)}
            </span>
            <span>Updated {new Date(dashboard.updated_at).toLocaleString()}</span>
          </div>
        </article>
      ))}
    </div>
  );
}
