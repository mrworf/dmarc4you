-- Dashboards (DATA_MODEL).
CREATE TABLE IF NOT EXISTS dashboards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    owner_user_id TEXT NOT NULL,
    created_by_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_dormant INTEGER NOT NULL DEFAULT 0,
    dormant_reason TEXT,
    FOREIGN KEY (owner_user_id) REFERENCES users(id),
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);

-- Dashboard domain scope: which domains the dashboard shows.
CREATE TABLE IF NOT EXISTS dashboard_domain_scope (
    dashboard_id TEXT NOT NULL,
    domain_id TEXT NOT NULL,
    PRIMARY KEY (dashboard_id, domain_id),
    FOREIGN KEY (dashboard_id) REFERENCES dashboards(id),
    FOREIGN KEY (domain_id) REFERENCES domains(id)
);
