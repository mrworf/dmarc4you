-- Rebuild aggregate record FTS to include resolved host fields and keep updates in sync.

DROP TRIGGER IF EXISTS fts_aggregate_records_insert;
DROP TRIGGER IF EXISTS fts_aggregate_records_delete;
DROP TRIGGER IF EXISTS fts_aggregate_records_update;
DROP TABLE IF EXISTS aggregate_records_fts;

CREATE VIRTUAL TABLE IF NOT EXISTS aggregate_records_fts USING fts5(
    source_ip,
    resolved_name,
    resolved_name_domain,
    header_from,
    envelope_from,
    envelope_to,
    org_name,
    content='',
    contentless_delete=1
);

INSERT INTO aggregate_records_fts(
    rowid,
    source_ip,
    resolved_name,
    resolved_name_domain,
    header_from,
    envelope_from,
    envelope_to,
    org_name
)
SELECT
    rec.rowid,
    rec.source_ip,
    rec.resolved_name,
    rec.resolved_name_domain,
    rec.header_from,
    rec.envelope_from,
    rec.envelope_to,
    ar.org_name
FROM aggregate_report_records rec
JOIN aggregate_reports ar ON rec.aggregate_report_id = ar.id;

CREATE TRIGGER IF NOT EXISTS fts_aggregate_records_insert
AFTER INSERT ON aggregate_report_records
BEGIN
    INSERT INTO aggregate_records_fts(
        rowid,
        source_ip,
        resolved_name,
        resolved_name_domain,
        header_from,
        envelope_from,
        envelope_to,
        org_name
    )
    SELECT
        NEW.rowid,
        NEW.source_ip,
        NEW.resolved_name,
        NEW.resolved_name_domain,
        NEW.header_from,
        NEW.envelope_from,
        NEW.envelope_to,
        ar.org_name
    FROM aggregate_reports ar
    WHERE ar.id = NEW.aggregate_report_id;
END;

CREATE TRIGGER IF NOT EXISTS fts_aggregate_records_delete
AFTER DELETE ON aggregate_report_records
BEGIN
    DELETE FROM aggregate_records_fts WHERE rowid = OLD.rowid;
END;

CREATE TRIGGER IF NOT EXISTS fts_aggregate_records_update
AFTER UPDATE OF source_ip, resolved_name, resolved_name_domain, header_from, envelope_from, envelope_to, aggregate_report_id
ON aggregate_report_records
BEGIN
    DELETE FROM aggregate_records_fts WHERE rowid = OLD.rowid;
    INSERT INTO aggregate_records_fts(
        rowid,
        source_ip,
        resolved_name,
        resolved_name_domain,
        header_from,
        envelope_from,
        envelope_to,
        org_name
    )
    SELECT
        NEW.rowid,
        NEW.source_ip,
        NEW.resolved_name,
        NEW.resolved_name_domain,
        NEW.header_from,
        NEW.envelope_from,
        NEW.envelope_to,
        ar.org_name
    FROM aggregate_reports ar
    WHERE ar.id = NEW.aggregate_report_id;
END;
