-- Forensic (failure) reports table for DMARC ruf reports.
CREATE TABLE IF NOT EXISTS forensic_reports (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    source_ip TEXT,
    arrival_time TEXT,
    org_name TEXT,
    header_from TEXT,
    envelope_from TEXT,
    envelope_to TEXT,
    spf_result TEXT,
    dkim_result TEXT,
    dmarc_result TEXT,
    failure_type TEXT,
    job_item_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(report_id, domain),
    FOREIGN KEY (job_item_id) REFERENCES ingest_job_items(id)
);

CREATE INDEX IF NOT EXISTS idx_forensic_domain ON forensic_reports(domain);
CREATE INDEX IF NOT EXISTS idx_forensic_arrival ON forensic_reports(arrival_time);
