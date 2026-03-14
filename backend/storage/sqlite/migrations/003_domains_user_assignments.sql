-- Domains: active/archived; nullable archived/retention fields for Phase 5.
CREATE TABLE IF NOT EXISTS domains (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    archived_at TEXT,
    archived_by_user_id TEXT,
    retention_days INTEGER,
    retention_delete_at TEXT,
    retention_paused INTEGER DEFAULT 0,
    retention_paused_at TEXT,
    retention_pause_reason TEXT,
    retention_remaining_seconds INTEGER
);

-- User-domain assignments: non-super-admin visibility.
CREATE TABLE IF NOT EXISTS user_domain_assignments (
    user_id TEXT NOT NULL,
    domain_id TEXT NOT NULL,
    assigned_by_user_id TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    PRIMARY KEY (user_id, domain_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (domain_id) REFERENCES domains(id)
);
