-- Index for aggregate report list queries (domain + time).
CREATE INDEX IF NOT EXISTS idx_aggregate_reports_domain_date ON aggregate_reports(domain, date_begin);
