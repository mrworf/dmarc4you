-- FTS5 virtual table for free-text search over aggregate report records.
-- Indexes: source_ip, header_from, envelope_from, envelope_to, and org_name (from parent report).

CREATE VIRTUAL TABLE IF NOT EXISTS aggregate_records_fts USING fts5(
    source_ip,
    header_from,
    envelope_from,
    envelope_to,
    org_name,
    content='',
    contentless_delete=1
);

-- Populate FTS table from existing records.
INSERT INTO aggregate_records_fts(rowid, source_ip, header_from, envelope_from, envelope_to, org_name)
SELECT rec.rowid, rec.source_ip, rec.header_from, rec.envelope_from, rec.envelope_to, ar.org_name
FROM aggregate_report_records rec
JOIN aggregate_reports ar ON rec.aggregate_report_id = ar.id;

-- Trigger: keep FTS in sync on INSERT.
CREATE TRIGGER IF NOT EXISTS fts_aggregate_records_insert
AFTER INSERT ON aggregate_report_records
BEGIN
    INSERT INTO aggregate_records_fts(rowid, source_ip, header_from, envelope_from, envelope_to, org_name)
    SELECT NEW.rowid, NEW.source_ip, NEW.header_from, NEW.envelope_from, NEW.envelope_to, ar.org_name
    FROM aggregate_reports ar WHERE ar.id = NEW.aggregate_report_id;
END;

-- Trigger: keep FTS in sync on DELETE.
CREATE TRIGGER IF NOT EXISTS fts_aggregate_records_delete
AFTER DELETE ON aggregate_report_records
BEGIN
    INSERT INTO aggregate_records_fts(aggregate_records_fts, rowid, source_ip, header_from, envelope_from, envelope_to, org_name)
    VALUES('delete', OLD.rowid, OLD.source_ip, OLD.header_from, OLD.envelope_from, OLD.envelope_to,
           (SELECT org_name FROM aggregate_reports WHERE id = OLD.aggregate_report_id));
END;
