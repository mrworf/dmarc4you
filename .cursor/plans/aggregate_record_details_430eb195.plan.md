---
name: Aggregate Record Details
overview: Extend aggregate report parsing to extract per-record details (source IP, disposition, SPF/DKIM results) and implement the POST /api/v1/search endpoint with include/exclude filters, enabling meaningful dashboard filtering and drill-down.
todos:
  - id: migration
    content: Create migration 010_aggregate_records.sql with aggregate_report_records table and indexes
    status: completed
  - id: parser
    content: Extend aggregate_parser.py to extract record-level details from XML
    status: completed
  - id: ingest
    content: Update ingest_service.py to persist aggregate_report_records rows
    status: completed
  - id: search-service
    content: Add search_records() function in search_service.py with include/exclude filtering
    status: completed
  - id: search-api
    content: Add POST /api/v1/search endpoint in reports.py handler
    status: completed
  - id: tests
    content: Add unit tests for parser and integration tests for search endpoint
    status: completed
---

# Aggregate Record Details and Structured Search

## Current Gap

The aggregate parser ([backend/ingest/aggregate_parser.py](backend/ingest/aggregate_parser.py)) only extracts report-level metadata (org_name, report_id, dates, domain). Per the DATA_MODEL.md spec, it should also store **record-level details** from each `<record>` element:

- source_ip, message_count, disposition
- dkim_result, spf_result
- header_from, envelope_from, envelope_to

The POST /api/v1/search endpoint (specified in [docs/API_V1.md](docs/API_V1.md)) is not yet implemented. It should support:

- Domain and time range filtering
- Include/exclude filters (e.g., `spf_result: ["fail"]`, `disposition: ["none"]`)
- Pagination and sorting

## Implementation Approach

### 1. Database Schema

Add new table `aggregate_report_records` storing one row per `<record>` element:

```sql
CREATE TABLE aggregate_report_records (
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
    FOREIGN KEY (aggregate_report_id) REFERENCES aggregate_reports(id)
);
CREATE INDEX idx_arr_report ON aggregate_report_records(aggregate_report_id);
CREATE INDEX idx_arr_domain_time ON aggregate_report_records(source_ip);
```

### 2. Parser Enhancement

Extend `parse_aggregate()` to return a `records` list with extracted fields from each `<record>` element in the XML.

### 3. Ingest Service Update

Store both the aggregate_report row and all aggregate_report_records rows during ingest processing.

### 4. Search Service + API

Implement `POST /api/v1/search`:

```python
{
  "domains": ["example.com"],
  "from": "...", "to": "...",
  "include": {"spf_result": ["fail"]},
  "exclude": {"disposition": ["none"]},
  "page": 1, "page_size": 50
}
```

Returns records from `aggregate_report_records` joined with `aggregate_reports` for domain scoping.

## Files to Create/Edit

- **Create:** `backend/storage/sqlite/migrations/010_aggregate_records.sql`
- **Edit:** `backend/ingest/aggregate_parser.py` - extract record details
- **Edit:** `backend/services/ingest_service.py` - persist records
- **Edit:** `backend/services/search_service.py` - add `search_records()` function
- **Edit:** `backend/api/v1/handlers/reports.py` - add `POST /search` endpoint
- **Create:** `tests/test_aggregate_parser_records.py`
- **Edit:** `tests/integration/test_search.py` - add search endpoint tests

## Acceptance Criteria

1. Aggregate XML parsing extracts all `<record>` elements with source_ip, count, disposition, dkim_result, spf_result
2. Ingest stores record details in `aggregate_report_records` table
3. `POST /api/v1/search` returns records filtered by include/exclude conditions
4. Domain scoping enforced on search results (user only sees records for allowed domains)
5. Existing ingest and aggregate list functionality unchanged

## Validation Steps

- Unit test for extended aggregate parser with multi-record XML
- Integration test for POST /search with include/exclude filters
- Integration test verifying domain scoping on search results
- Verify existing tests still pass