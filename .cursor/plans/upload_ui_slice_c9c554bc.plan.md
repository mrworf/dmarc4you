---
name: Upload UI Slice
overview: Add /app/upload route allowing users to submit DMARC reports via web form. Supports paste XML or file selection, calls existing POST /api/v1/reports/ingest, shows job status link on success.
todos:
  - id: upload-view-html
    content: "Add #upload-view to index.html with textarea, file input, submit button, success/error areas, and nav link"
    status: completed
  - id: upload-js
    content: Add showUpload(), file reading, base64 encoding, POST to /api/v1/reports/ingest, success/error handlers in app.js
    status: completed
  - id: gzip-detection
    content: "Detect gzip files by extension or magic bytes and set content_encoding: gzip in request"
    status: completed
  - id: docs-update
    content: Mark /app/upload as implemented in FRONTEND_AND_DASHBOARDS.md
    status: completed
  - id: manual-test
    content: "Manual smoke test: paste XML, upload XML, upload gzip, verify job links work"
    status: pending
---

# Upload UI Slice

## Current Gap

The ingest API ([backend/api/v1/handlers/reports.py](backend/api/v1/handlers/reports.py)) accepts JSON-envelope report submissions via session or API key auth. The CLI and programmatic clients can use this, but web users have no UI to submit reports directly. The route `/app/upload` is listed in [docs/FRONTEND_AND_DASHBOARDS.md](docs/FRONTEND_AND_DASHBOARDS.md) but not implemented.

## Implementation Approach

### Frontend Only

No backend changes needed. The existing `POST /api/v1/reports/ingest` endpoint accepts:

```json
{
  "source": "web",
  "reports": [
    {
      "content_type": "application/xml",
      "content_encoding": "none",
      "content_transfer_encoding": "base64",
      "content": "<base64-encoded XML>"
    }
  ]
}
```

The UI will:

1. Accept XML via textarea paste **or** file input (single file for simplicity)
2. Base64-encode the content client-side
3. POST to `/api/v1/reports/ingest` with session auth
4. On success (202/200), show job_id with link to `/app/ingest-jobs/{job_id}`
5. On error (400/401/403), show error message

### Supported formats this slice

- Plain XML paste or file
- Gzip-compressed XML file (detect by file extension or magic bytes)

Out of scope: drag-and-drop, multiple files at once, ZIP archives.

## Files to Create/Edit

- **Edit:** [frontend/index.html](frontend/index.html) - Add `#upload-view` with form (textarea for paste, file input, submit button), success/error display, nav link
- **Edit:** [frontend/js/app.js](frontend/js/app.js) - Add `showUpload()`, `loadUploadPage()`, file reading with FileReader API, base64 encoding, POST to ingest endpoint, success/error handling
- **Edit:** [docs/FRONTEND_AND_DASHBOARDS.md](docs/FRONTEND_AND_DASHBOARDS.md) - Mark `/app/upload` as implemented

## Acceptance Criteria

1. `/app/upload` view accessible from nav (link visible to all authenticated users)
2. User can paste XML into textarea and submit; on success sees job_id with link to job detail
3. User can select an XML file and submit; same success behavior
4. User can select a .xml.gz file; content is detected as gzip, encoded appropriately
5. 401 if not logged in; 400 on malformed input shows user-friendly error
6. Existing ingest tests continue to pass (no backend changes)

## Validation Steps

- Manual: log in, paste valid aggregate XML, submit, verify job created and link works
- Manual: log in, upload .xml file, submit, verify job created
- Manual: log in, upload .xml.gz file, submit, verify job created
- Manual: paste invalid content, verify error message shown
- Run existing ingest tests: `pytest tests/integration/test_ingest.py`