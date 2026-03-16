ALTER TABLE aggregate_reports ADD COLUMN contact_email TEXT;
ALTER TABLE aggregate_reports ADD COLUMN extra_contact_info TEXT;
ALTER TABLE aggregate_reports ADD COLUMN error_messages_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE aggregate_reports ADD COLUMN adkim TEXT;
ALTER TABLE aggregate_reports ADD COLUMN aspf TEXT;
ALTER TABLE aggregate_reports ADD COLUMN policy_p TEXT;
ALTER TABLE aggregate_reports ADD COLUMN policy_sp TEXT;
ALTER TABLE aggregate_reports ADD COLUMN policy_pct INTEGER;
ALTER TABLE aggregate_reports ADD COLUMN policy_fo TEXT;

ALTER TABLE aggregate_report_records ADD COLUMN country_code TEXT;
ALTER TABLE aggregate_report_records ADD COLUMN country_name TEXT;
ALTER TABLE aggregate_report_records ADD COLUMN geo_provider TEXT;

ALTER TABLE forensic_reports ADD COLUMN country_code TEXT;
ALTER TABLE forensic_reports ADD COLUMN country_name TEXT;
ALTER TABLE forensic_reports ADD COLUMN geo_provider TEXT;

ALTER TABLE dashboards ADD COLUMN visible_columns_json TEXT NOT NULL DEFAULT '[]';

CREATE TABLE IF NOT EXISTS aggregate_record_policy_overrides (
    id TEXT PRIMARY KEY,
    aggregate_record_id TEXT NOT NULL,
    reason_type TEXT,
    comment TEXT,
    FOREIGN KEY (aggregate_record_id) REFERENCES aggregate_report_records(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_arpo_record ON aggregate_record_policy_overrides(aggregate_record_id);

CREATE TABLE IF NOT EXISTS aggregate_record_auth_results (
    id TEXT PRIMARY KEY,
    aggregate_record_id TEXT NOT NULL,
    auth_method TEXT NOT NULL,
    domain TEXT,
    selector TEXT,
    scope TEXT,
    result TEXT,
    human_result TEXT,
    FOREIGN KEY (aggregate_record_id) REFERENCES aggregate_report_records(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_araa_record ON aggregate_record_auth_results(aggregate_record_id);
CREATE INDEX IF NOT EXISTS idx_araa_method ON aggregate_record_auth_results(auth_method);
