CREATE TABLE IF NOT EXISTS domain_maintenance_jobs (
    id TEXT PRIMARY KEY,
    domain_id TEXT NOT NULL,
    domain_name TEXT NOT NULL,
    action TEXT NOT NULL,
    actor_user_id TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    state TEXT NOT NULL DEFAULT 'queued',
    reports_scanned INTEGER NOT NULL DEFAULT 0,
    reports_skipped INTEGER NOT NULL DEFAULT 0,
    records_updated INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    summary TEXT,
    FOREIGN KEY (domain_id) REFERENCES domains(id),
    FOREIGN KEY (actor_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_domain_maintenance_jobs_domain_submitted
    ON domain_maintenance_jobs(domain_id, submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_domain_maintenance_jobs_state_submitted
    ON domain_maintenance_jobs(state, submitted_at);

CREATE INDEX IF NOT EXISTS idx_domain_maintenance_jobs_actor_submitted
    ON domain_maintenance_jobs(actor_user_id, submitted_at DESC);
