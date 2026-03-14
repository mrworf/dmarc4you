-- Ingest jobs (DATA_MODEL).
CREATE TABLE IF NOT EXISTS ingest_jobs (
    id TEXT PRIMARY KEY,
    actor_type TEXT NOT NULL DEFAULT 'user',
    actor_user_id TEXT NOT NULL,
    actor_api_key_id TEXT,
    submitted_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    state TEXT NOT NULL DEFAULT 'queued',
    last_error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0
);

-- Ingest job items: one per report in envelope.
CREATE TABLE IF NOT EXISTS ingest_job_items (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    raw_content_type TEXT,
    raw_content_encoding TEXT,
    raw_content_transfer_encoding TEXT,
    raw_content TEXT NOT NULL,
    report_type_detected TEXT,
    domain_detected TEXT,
    status TEXT,
    status_reason TEXT,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (job_id) REFERENCES ingest_jobs(id)
);

-- Normalized aggregate reports; dedupe on (report_id, domain).
CREATE TABLE IF NOT EXISTS aggregate_reports (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    org_name TEXT,
    domain TEXT NOT NULL,
    date_begin INTEGER NOT NULL,
    date_end INTEGER NOT NULL,
    job_item_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(report_id, domain),
    FOREIGN KEY (job_item_id) REFERENCES ingest_job_items(id)
);
