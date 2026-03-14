-- Dashboard user access: sharing dashboards with viewers/managers.
CREATE TABLE IF NOT EXISTS dashboard_user_access (
    dashboard_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    access_level TEXT NOT NULL CHECK (access_level IN ('viewer', 'manager')),
    granted_by_user_id TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    PRIMARY KEY (dashboard_id, user_id),
    FOREIGN KEY (dashboard_id) REFERENCES dashboards(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (granted_by_user_id) REFERENCES users(id)
);
