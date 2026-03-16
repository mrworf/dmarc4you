ALTER TABLE users ADD COLUMN full_name TEXT;
ALTER TABLE users ADD COLUMN email TEXT;

ALTER TABLE aggregate_report_records ADD COLUMN resolved_name TEXT;
ALTER TABLE aggregate_report_records ADD COLUMN resolved_name_domain TEXT;

ALTER TABLE forensic_reports ADD COLUMN resolved_name TEXT;
ALTER TABLE forensic_reports ADD COLUMN resolved_name_domain TEXT;

CREATE INDEX IF NOT EXISTS idx_arr_resolved_name ON aggregate_report_records(resolved_name);
CREATE INDEX IF NOT EXISTS idx_arr_resolved_name_domain ON aggregate_report_records(resolved_name_domain);
CREATE INDEX IF NOT EXISTS idx_forensic_resolved_name ON forensic_reports(resolved_name);
CREATE INDEX IF NOT EXISTS idx_forensic_resolved_name_domain ON forensic_reports(resolved_name_domain);
