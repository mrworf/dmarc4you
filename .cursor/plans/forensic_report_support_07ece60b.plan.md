---
name: Forensic Report Support
overview: Add forensic (ruf) report parsing, storage, and API endpoint to complete Phase 2's "aggregate and forensic parsing" deliverable. This enables ingestion and querying of DMARC failure reports alongside the existing aggregate reports.
todos:
  - id: schema
    content: Create 011_forensic_reports.sql migration with table and indexes
    status: completed
  - id: parser
    content: Implement forensic_parser.py with parse_forensic() function
    status: completed
  - id: parser-tests
    content: Add unit tests for forensic parser edge cases
    status: completed
  - id: dedupe
    content: Extend dedupe.py to handle forensic report deduplication
    status: completed
  - id: runner
    content: Update runner.py to detect report type and dispatch to correct parser/persistence
    status: completed
  - id: api
    content: Add GET /api/v1/reports/forensic endpoint with domain scoping and pagination
    status: completed
  - id: integration-tests
    content: Add integration tests for forensic ingest flow
    status: completed
  - id: docs
    content: Update API_V1.md to document the forensic endpoint
    status: completed
---

# Forensic Report Parsing Slice

## Context

The product spec explicitly states:

> "Ingest DMARC reports from XML, compressed XML, and RFC-compliant email messages with report attachments."

> "Normalize aggregate and forensic data into a queryable backend model."

Currently only aggregate (rua) parsing exists. The API doc notes `GET /api/v1/reports/forensic` as "not yet implemented." The [DATA_MODEL.md](docs/DATA_MODEL.md) already specifies forensic report fields (lines 163-176).

## Scope

Add end-to-end forensic report support:

- Schema migration for `forensic_reports` table
- Parser for DMARC failure report XML format
- Ingest pipeline integration (auto-detect report type)
- List/query API endpoint
- Tests for parser and integration

## Files to Create

- `backend/storage/sqlite/migrations/011_forensic_reports.sql` - new table
- `backend/ingest/forensic_parser.py` - XML parser
- `tests/test_forensic_parser.py` - parser unit tests

## Files to Edit

- [backend/jobs/runner.py](backend/jobs/runner.py) - detect report type, dispatch to correct parser
- [backend/api/v1/handlers/reports.py](backend/api/v1/handlers/reports.py) - add `GET /api/v1/reports/forensic` endpoint
- [backend/services/search_service.py](backend/services/search_service.py) - add forensic query function
- [backend/ingest/dedupe.py](backend/ingest/dedupe.py) - add forensic dedupe check
- [docs/API_V1.md](docs/API_V1.md) - update forensic endpoint from "not yet implemented" to documented
- [tests/integration/test_ingest.py](tests/integration/test_ingest.py) - add forensic ingest test

## Schema (011_forensic_reports.sql)

Based on [DATA_MODEL.md](docs/DATA_MODEL.md) lines 163-176:

```sql
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
```

## Parser Logic

DMARC forensic reports use AFRF (Authentication Failure Reporting Format) per RFC 7489. The parser will:

1. Parse the XML envelope
2. Extract: reported domain, source IP, arrival time, org name, identifiers, auth results, failure type
3. Return structured dict or None on parse error

## Ingest Integration

Update `_process_one_item()` in [runner.py](backend/jobs/runner.py):

1. Try `parse_aggregate()` first (current behavior)
2. If None, try `parse_forensic()`
3. Set `report_type_detected` to `'aggregate'` or `'forensic'` accordingly
4. Route to appropriate persistence logic

## Acceptance Criteria

- Forensic XML parses correctly and persists to `forensic_reports`
- Dedupe works for forensic reports (same report_id + domain = duplicate)
- `GET /api/v1/reports/forensic` returns domain-scoped results with pagination
- Mixed ingest envelope with aggregate + forensic reports processes both
- Invalid forensic XML returns `status: invalid` on the job item
- Parser rejects oversized payloads

## Validation Steps

- `pytest tests/test_forensic_parser.py` - parser unit tests
- `pytest tests/integration/test_ingest.py` - forensic ingest integration
- Manual: submit forensic report via API, verify in DB and via list endpoint