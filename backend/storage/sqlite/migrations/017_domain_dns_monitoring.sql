ALTER TABLE domains ADD COLUMN monitoring_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE domains ADD COLUMN monitoring_last_checked_at TEXT;
ALTER TABLE domains ADD COLUMN monitoring_next_check_at TEXT;
ALTER TABLE domains ADD COLUMN monitoring_last_change_at TEXT;
ALTER TABLE domains ADD COLUMN monitoring_last_triggered_at TEXT;
ALTER TABLE domains ADD COLUMN monitoring_failure_active INTEGER NOT NULL DEFAULT 0;
ALTER TABLE domains ADD COLUMN monitoring_last_failure_at TEXT;
ALTER TABLE domains ADD COLUMN monitoring_last_failure_summary TEXT;

CREATE TABLE IF NOT EXISTS domain_monitoring_dkim_selectors (
    domain_id TEXT NOT NULL,
    selector TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (domain_id, selector),
    FOREIGN KEY (domain_id) REFERENCES domains(id)
);

CREATE TABLE IF NOT EXISTS domain_monitoring_current_state (
    domain_id TEXT PRIMARY KEY,
    checked_at TEXT NOT NULL,
    observed_state_json TEXT NOT NULL,
    dmarc_record_raw TEXT,
    spf_record_raw TEXT,
    dkim_records_json TEXT NOT NULL DEFAULT '[]',
    ttl_seconds INTEGER,
    error_summary TEXT,
    FOREIGN KEY (domain_id) REFERENCES domains(id)
);

CREATE TABLE IF NOT EXISTS domain_monitoring_history (
    id TEXT PRIMARY KEY,
    domain_id TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    previous_state_json TEXT,
    current_state_json TEXT NOT NULL,
    dmarc_record_raw TEXT,
    spf_record_raw TEXT,
    dkim_records_json TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (domain_id) REFERENCES domains(id)
);

CREATE INDEX IF NOT EXISTS idx_domain_monitoring_history_domain_changed
    ON domain_monitoring_history(domain_id, changed_at DESC);

ALTER TABLE domain_maintenance_jobs RENAME TO domain_maintenance_jobs_old;

CREATE TABLE domain_maintenance_jobs (
    id TEXT PRIMARY KEY,
    domain_id TEXT NOT NULL,
    domain_name TEXT NOT NULL,
    action TEXT NOT NULL,
    actor_user_id TEXT,
    actor_api_key_id TEXT,
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
    FOREIGN KEY (actor_user_id) REFERENCES users(id),
    FOREIGN KEY (actor_api_key_id) REFERENCES api_keys(id)
);

INSERT INTO domain_maintenance_jobs (
    id,
    domain_id,
    domain_name,
    action,
    actor_user_id,
    actor_api_key_id,
    submitted_at,
    started_at,
    completed_at,
    state,
    reports_scanned,
    reports_skipped,
    records_updated,
    last_error,
    summary
)
SELECT
    id,
    domain_id,
    domain_name,
    action,
    actor_user_id,
    NULL,
    submitted_at,
    started_at,
    completed_at,
    state,
    reports_scanned,
    reports_skipped,
    records_updated,
    last_error,
    summary
FROM domain_maintenance_jobs_old;

DROP TABLE domain_maintenance_jobs_old;

CREATE INDEX IF NOT EXISTS idx_domain_maintenance_jobs_domain_submitted
    ON domain_maintenance_jobs(domain_id, submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_domain_maintenance_jobs_state_submitted
    ON domain_maintenance_jobs(state, submitted_at);

CREATE INDEX IF NOT EXISTS idx_domain_maintenance_jobs_actor_submitted
    ON domain_maintenance_jobs(actor_user_id, submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_domain_maintenance_jobs_api_key_submitted
    ON domain_maintenance_jobs(actor_api_key_id, submitted_at DESC);
