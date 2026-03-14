-- Per-record details from aggregate reports (one row per <record> element in XML).
CREATE TABLE IF NOT EXISTS aggregate_report_records (
    id TEXT PRIMARY KEY,
    aggregate_report_id TEXT NOT NULL,
    source_ip TEXT,
    count INTEGER NOT NULL DEFAULT 0,
    disposition TEXT,
    dkim_result TEXT,
    spf_result TEXT,
    header_from TEXT,
    envelope_from TEXT,
    envelope_to TEXT,
    FOREIGN KEY (aggregate_report_id) REFERENCES aggregate_reports(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_arr_report ON aggregate_report_records(aggregate_report_id);
CREATE INDEX IF NOT EXISTS idx_arr_spf ON aggregate_report_records(spf_result);
CREATE INDEX IF NOT EXISTS idx_arr_dkim ON aggregate_report_records(dkim_result);
CREATE INDEX IF NOT EXISTS idx_arr_disposition ON aggregate_report_records(disposition);
