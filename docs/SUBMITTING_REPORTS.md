# Submitting DMARC Reports

This guide explains how to submit DMARC aggregate (`rua`) and forensic (`ruf`) reports to the application.

## Overview

Reports can be submitted through three methods:

| Method | Authentication | Best For |
|--------|----------------|----------|
| **API** | API key (Bearer token) | Automated pipelines, mail server integration |
| **CLI** | API key | Manual uploads, scripting |
| **UI** | Browser session | Ad-hoc uploads, testing |

All submission methods create an asynchronous **ingest job**. The job processes each report individually, so a batch with multiple reports may have mixed outcomes (some accepted, some rejected).

## Supported Formats

The ingest pipeline accepts:

- **XML** — Plain DMARC aggregate or forensic XML
- **Gzip-compressed XML** — `.xml.gz` files
- **MIME/RFC822 email** — Emails with report attachments (as sent by reporting domains)
- **Multiple attachments** — MIME messages with several report files

## Prerequisites

For API and CLI submission, you need an **API key** with:

1. **Domain assignment** — The key must be assigned to the domain(s) in the reports
2. **Ingest scope** — The key must have the `reports:ingest` scope

### Creating an API Key

1. Log in as admin or super-admin
2. Navigate to **API Keys**
3. Click **Create API Key**
4. Enter a nickname (e.g., "mail-server-ingest")
5. Select the domains this key can submit reports for
6. Enable the `reports:ingest` scope
7. Click **Create**
8. **Copy and save the key** — It is shown only once

## Method 1: API Submission

Submit reports via HTTP POST to `/api/v1/reports/ingest`.

### Request Format

```http
POST /api/v1/reports/ingest HTTP/1.1
Host: localhost:8000
Authorization: Bearer <your-api-key>
Content-Type: application/json

{
  "source": "mail-server",
  "reports": [
    {
      "content_type": "application/xml",
      "content_encoding": "",
      "content_transfer_encoding": "base64",
      "content": "<base64-encoded-report>"
    }
  ]
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `source` | No | Identifier for the submission source (for logging) |
| `reports` | Yes | Array of report objects |
| `reports[].content_type` | Yes | MIME type: `application/xml`, `application/gzip`, `message/rfc822` |
| `reports[].content_encoding` | No | Compression: `gzip` or empty |
| `reports[].content_transfer_encoding` | Yes | Transfer encoding: `base64` |
| `reports[].content` | Yes | Base64-encoded report content |
| `reports[].metadata` | No | Optional metadata object |

### Response

```json
{
  "job_id": "job_abc123",
  "state": "queued"
}
```

The job runs asynchronously. Query the job status to see results.

### Example: curl

```bash
# Encode the report
CONTENT=$(base64 -w0 report.xml)

# Submit
curl -X POST http://localhost:8000/api/v1/reports/ingest \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"source\": \"curl\",
    \"reports\": [{
      \"content_type\": \"application/xml\",
      \"content_transfer_encoding\": \"base64\",
      \"content\": \"$CONTENT\"
    }]
  }"
```

### Example: Python

```python
import base64
import requests

api_key = "your-api-key"
url = "http://localhost:8000/api/v1/reports/ingest"

with open("report.xml", "rb") as f:
    content = base64.b64encode(f.read()).decode()

response = requests.post(
    url,
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "source": "python-script",
        "reports": [{
            "content_type": "application/xml",
            "content_transfer_encoding": "base64",
            "content": content,
        }]
    }
)

print(response.json())
```

## Method 2: CLI Submission

The CLI tool handles file reading, encoding, and API communication.

### Usage

```bash
python -m cli ingest [--api-key KEY] [--url URL] FILE [FILE ...]
```

### Options

| Option | Env Variable | Default | Description |
|--------|--------------|---------|-------------|
| `--api-key` | `DMARC4YOU_API_KEY` | — | API key (required) |
| `--url` | `DMARC4YOU_URL` | `http://localhost:8000` | API base URL |

### Examples

```bash
# Single file
python -m cli ingest --api-key YOUR_KEY report.xml

# Multiple files
python -m cli ingest --api-key YOUR_KEY *.xml.gz

# Using environment variables
export DMARC4YOU_API_KEY="your-key"
export DMARC4YOU_URL="https://dmarc.example.com"
python -m cli ingest report1.xml report2.xml.gz

# MIME email file
python -m cli ingest --api-key YOUR_KEY dmarc-report.eml
```

### Output

```
report.xml: submitted (job_id=job_abc123)
report2.xml.gz: submitted (job_id=job_def456)
bad-file.xml: failed (403 Forbidden) {"error": {"code": "forbidden"}}
```

Exit code is 0 if all files succeed, 1 if any fail.

## Method 3: UI Upload

Upload reports directly through the web interface.

### Steps

1. Log in to the application
2. Navigate to **Upload** (`/app/upload`)
3. Either:
   - **Paste** XML content into the text area, or
   - **Select one or more files** using the file picker (`.xml`, `.xml.gz`, `.eml`)
4. Click **Submit**
5. On success, a link to the ingest job appears

### Supported File Types

- `.xml` — Plain XML
- `.gz` — Gzip-compressed (detected by extension or magic bytes)
- `.eml` — MIME email with attachments

### Limitations

- Browser session authentication only (no API key)
- One or more files per submission
- Pasted XML and file uploads are mutually exclusive in a single submit action
- File size limited by browser/server configuration

## Checking Job Results

### Via API

```bash
# List your jobs
curl -H "Authorization: Bearer YOUR_KEY" \
  http://localhost:8000/api/v1/ingest-jobs

# Get job details
curl -H "Authorization: Bearer YOUR_KEY" \
  http://localhost:8000/api/v1/ingest-jobs/job_abc123
```

### Via UI

1. Navigate to **Ingest Jobs** (`/app/ingest-jobs`)
2. Click a job ID to view details
3. See per-report outcomes: accepted, rejected, duplicate, invalid

### Job States

| State | Description |
|-------|-------------|
| `queued` | Job created, waiting for processing |
| `running` | Job is being processed |
| `completed` | All reports processed successfully |
| `completed_with_warnings` | Some reports failed or were duplicates |
| `failed` | Job processing failed |

### Report Outcomes

| Outcome | Description |
|---------|-------------|
| `accepted` | Report parsed and stored |
| `duplicate` | Report already exists (by report_id + domain) |
| `rejected` | Domain not authorized or archived |
| `invalid` | Parse error or malformed content |

## Report Acceptance Rules

A report is accepted only if:

1. The domain in the report is configured in the system
2. The domain is **not archived**
3. The submitting API key (or user) has access to that domain
4. The report parses successfully
5. The report is not a duplicate (same `report_id` + domain)

Rejection reasons are logged internally but not exposed in API responses for security.

## Mail Server Integration

To automatically ingest DMARC reports from your mail server:

### Option 1: Pipe to CLI

Configure your MTA to pipe incoming DMARC reports to the CLI:

```bash
# Example procmail recipe
:0
* ^From:.*noreply-dmarc-support@google.com
| python -m cli ingest --api-key YOUR_KEY /dev/stdin
```

### Option 2: Periodic Script

Collect reports to a directory and process periodically:

```bash
#!/bin/bash
# /etc/cron.hourly/process-dmarc-reports

export DMARC4YOU_API_KEY="your-key"
export DMARC4YOU_URL="http://localhost:8000"

find /var/spool/dmarc-reports -name "*.xml*" -mmin +5 | while read f; do
  python -m cli ingest "$f" && rm "$f"
done
```

### Option 3: Direct API Integration

Integrate the API directly into your mail processing pipeline using the HTTP endpoint.

## Troubleshooting

### "403 Forbidden" on submission

- Verify the API key is correct
- Check the key has the `reports:ingest` scope
- Confirm the key is assigned to the domain(s) in the report

### "Job completed but report rejected"

- The domain may not be configured — add it in Domains
- The domain may be archived — only super-admin can restore it
- The API key may not have access to that domain

### "Duplicate" status

- The report was already ingested (same `report_id` and domain)
- This is normal for retries and prevents double-counting

### "Invalid" status

- The XML is malformed or not a valid DMARC report
- Check the report format matches DMARC aggregate or forensic schema
- For MIME files, ensure attachments are properly encoded

## See Also

- [API v1 Specification](API_V1.md) — Full API reference for ingest and job endpoints
- [Getting Started](GETTING_STARTED.md) — Installation and initial setup
- [Security and Audit](SECURITY_AND_AUDIT.md) — API key security and audit logging
