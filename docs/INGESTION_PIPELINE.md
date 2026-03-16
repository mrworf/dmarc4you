# Ingestion Pipeline

## Supported inputs

The system must ingest DMARC reports from:

- plain XML
- compressed XML (`gzip`, `zip` where practical)
- RFC-compliant email messages with one or more report attachments
- structured JSON envelope submitted to the REST API

The CLI may read input from a file or STDIN.

## Processing model

Ingest is asynchronous. Submission creates a job, and the background runner processes the job later.

## Pipeline stages

### 1. Envelope acceptance

The API accepts a JSON request containing one or more reports. Each report may include:

- encoded content
- content encoding metadata
- source metadata (advisory only)

### 2. Job creation

Persist:

- actor identity
- raw request envelope metadata
- job state = `queued`
- one `ingest_job_item` per report unit in the envelope

### 3. Job execution

For each job item:

1. decode transfer encoding
2. decompress if required
3. classify content as XML or MIME email
4. extract attachments if email
5. recursively process supported compressed attachments within configured limits
6. detect aggregate vs forensic report
7. parse XML safely
8. determine authoritative domain(s)
9. verify domain is configured and not archived
10. verify actor/API key is authorized for that domain
11. dedupe
12. perform best-effort reverse DNS enrichment for source IPs
13. archive raw artifact if enabled
14. persist normalized data
15. persist per-item outcome
16. write audit/log events as needed

## Per-report outcome rules

Possible statuses:

- `accepted`
- `duplicate`
- `invalid`
- `rejected`

Common reasons:

- unconfigured domain
- unauthorized domain
- archived domain
- malformed payload
- unsupported encoding
- duplicate report

## Reverse DNS enrichment

- Ingest attempts reverse DNS resolution for aggregate and forensic source IPs
- Lookup failure or timeout never rejects the report
- Normalized rows keep the original IP and store nullable `resolved_name` / `resolved_name_domain`

## Partial acceptance

Batches are processed best-effort per report.

- accepted reports continue
- unauthorized or archived reports do not stop unrelated reports
- malformed reports do not poison the entire batch
- duplicates are recorded and skipped individually

## External vs internal error detail

External API responses should be safe and generic.

Internal logs/audit should retain the detailed reason, including:

- archived domain rejection
- API key unauthorized domain attempt
- invalid compression or parse errors

## Dedupe guidance

Dedupe keys should be deterministic.

Examples:

- aggregate: reporting org + report id + policy domain + report date range
- forensic: stable report/message identifiers when present, with content-hash fallback

## Restart-safe execution

- persist job and per-item states before/after major transitions
- treat `processing` jobs as recoverable on restart
- resume only unfinished items
- rely on dedupe and checkpoints to keep retries idempotent
