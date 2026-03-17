ALTER TABLE aggregate_report_records ADD COLUMN dkim_alignment TEXT;
ALTER TABLE aggregate_report_records ADD COLUMN spf_alignment TEXT;
ALTER TABLE aggregate_report_records ADD COLUMN dmarc_alignment TEXT;

CREATE INDEX IF NOT EXISTS idx_arr_dkim_alignment ON aggregate_report_records(dkim_alignment);
CREATE INDEX IF NOT EXISTS idx_arr_spf_alignment ON aggregate_report_records(spf_alignment);
CREATE INDEX IF NOT EXISTS idx_arr_dmarc_alignment ON aggregate_report_records(dmarc_alignment);
