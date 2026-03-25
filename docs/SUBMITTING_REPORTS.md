# Submitting DMARC Reports

DMARCWatch accepts asynchronous report submission through the REST API, the local CLI, and the browser upload screen.

## What the ingest pipeline accepts

- Plain XML DMARC reports
- Gzip-compressed XML
- ZIP archives containing supported report payloads
- MIME/RFC822 email messages with DMARC report attachments

Every submission creates an ingest job. Outcomes are tracked per report item, so a single batch can contain accepted, duplicate, invalid, and rejected items.

## API submission

Endpoint:

- `POST /api/v1/reports/ingest`

Authentication:

- Session cookie, or
- `Authorization: Bearer <api-key>`

For API key submission, the key must include the `reports:ingest` scope and be assigned to the relevant domain or domains.

Example request:

```json
{
  "source": "mail-server",
  "reports": [
    {
      "content_type": "application/xml",
      "content_encoding": "",
      "content_transfer_encoding": "base64",
      "content": "PD94bWwgdmVyc2lvbj0iMS4wIj8+..."
    }
  ]
}
```

Example response:

```json
{
  "job_id": "job_abc123",
  "state": "queued"
}
```

Example `curl`:

```bash
CONTENT=$(base64 -w0 report.xml)

curl -X POST http://127.0.0.1:8000/api/v1/reports/ingest \
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

## CLI submission

Usage:

```bash
python -m cli ingest [--api-key KEY] [--url URL] FILE [FILE ...]
```

Options:

- `--api-key` or `DMARC4YOU_API_KEY`
- `--url` or `DMARC4YOU_URL` (defaults to `http://localhost:8000`)

Examples:

```bash
python -m cli ingest --api-key YOUR_KEY report.xml
python -m cli ingest --api-key YOUR_KEY *.xml.gz *.zip
python -m cli ingest --api-key YOUR_KEY dmarc-report.eml
```

The CLI detects basic content type and compression automatically, base64-encodes the file, and submits it to the ingest endpoint.

Exit behavior:

- `0` when all files were submitted successfully
- `1` when any file failed

## Browser upload

Use the Upload page at `/upload` when you want to submit files interactively with a browser session.

Supported upload paths:

- paste XML directly
- upload one or more files

Common file types:

- `.xml`
- `.gz`
- `.zip`
- `.eml`

## Checking job status

API endpoints:

- `GET /api/v1/ingest-jobs`
- `GET /api/v1/ingest-jobs/{job_id}`

Example:

```bash
curl -H "Authorization: Bearer YOUR_KEY" \
  http://127.0.0.1:8000/api/v1/ingest-jobs
```

Typical job item statuses:

- `accepted`
- `duplicate`
- `invalid`
- `rejected`

## Common rejection causes

- the report domain is not configured
- the report domain is archived
- the session user or API key is not authorized for that domain
- the payload cannot be parsed
- the report is a duplicate
