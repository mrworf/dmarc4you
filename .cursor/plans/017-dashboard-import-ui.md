# Plan: Dashboard import UI (Phase 6)

## Goal

Add a **minimal UI** for dashboard import on the frontend: paste YAML (or upload), build domain remap from current user's domains, and call **POST /api/v1/dashboards/import**. Show created dashboard or error. No new backend; reuse existing import API.

## Why this slice

- Phase 6: "dashboard YAML import/export with domain remapping". Export and import API are done (slices 012, 013). FRONTEND_AND_DASHBOARDS: "Import flow: upload YAML, require domain remapping, validate importer access, create dashboard owned by importer." This slice adds the UI so users can complete the flow without calling the API directly.

## Scope (in)

- **Dashboards view**: Add an "Import dashboard" section or link that reveals a form: (1) textarea or file input for YAML (export-shaped: name, description, domains list of names); (2) after parsing or pasting, show the list of domain **names** from the YAML and for each a dropdown (or list) to select the **local domain** (from GET /api/v1/domains) to map to; (3) Submit calls POST /api/v1/dashboards/import with body `{ yaml, domain_remap }`. On 201: show success and link to the new dashboard (or redirect); on 400/403: show error message.
- **Parsing**: Client can parse pasted YAML (e.g. JS YAML lib or simple regex) to extract domain names for the remap UI; or require user to select mappings manually after pasting. Simplest: paste YAML, fetch current user's domains, show one dropdown per "logical" domain — but we don't know domain names until we parse YAML. So: on paste, parse YAML (use a small YAML parser or `JSON.parse` if we accept JSON too); extract `domains` array; for each name show a row "&lt;name&gt; → [dropdown of local domains]". Build `domain_remap` from selections and POST. If parsing fails, show "Invalid YAML".
- **Access**: Same as create dashboard — user must have access to all mapped domains. Import is only shown to users who can create dashboards (admin, super-admin, manager with domains).
- **Tests**: Optional: no new backend; manual or E2E. Or add a minimal integration test that uses the API (import) from the test client; no frontend test required in this slice if we keep scope to UI only.

## Scope (out)

- File upload (drag-and-drop); paste-only is enough for this slice.
- Widget definitions in YAML; only name, description, domains.

---

## Files to create or edit

### Frontend

| Path | Action |
|------|--------|
| `frontend/index.html` | Add import section: e.g. "Import dashboard" link/button, collapse or inline form with textarea (YAML), placeholders for "Domain mapping" (filled after parse), Submit button, error/success message area. |
| `frontend/js/app.js` | On "Import" show form. On paste/change of YAML textarea: parse YAML (e.g. use a lightweight parser — check if one is already available or use dynamic import / minimal impl); extract `domains`; fetch GET /api/v1/domains; render one row per YAML domain name with dropdown of local domains (id). Build domain_remap: `{ [name]: selected_domain_id }`. Submit: POST /api/v1/dashboards/import with { yaml, domain_remap }; on 201 show success + link to dashboard or navigate to it; on 4xx show error. |
| `frontend/css/main.css` | Optional: style for import form (textarea, mapping table). |

### Docs

| Path | Action |
|------|--------|
| `docs/FRONTEND_AND_DASHBOARDS.md` or none | Optional: note that import UI is available on dashboards page. |

### Tests

| Path | Action |
|------|--------|
| None or `tests/integration/test_dashboards.py` | No new backend; existing import API tests cover behavior. Optional: add one test that imports via API and then fetches dashboard to assert it exists (already covered). Skip new tests if scope is UI-only. |

---

## Acceptance criteria

1. From the dashboards view, user can open an "Import dashboard" form (link or section).
2. User can paste YAML (name, description, domains). After paste, the UI shows the list of domain names from the YAML and for each a way to choose a local domain (dropdown populated from GET /api/v1/domains).
3. User submits; frontend sends POST /api/v1/dashboards/import with the YAML and domain_remap built from selections. On 201: user sees success and can navigate to the new dashboard. On 400 or 403: user sees an error message.
4. Invalid YAML shows a clear message (e.g. "Invalid YAML").
5. Import option is visible to users who can create dashboards (same visibility as "New dashboard" — admin, super-admin, manager with domains).

---

## Tests and validation

1. Manual: Log in as admin, go to Dashboards, open Import, paste valid export YAML, select mappings, submit → dashboard created. Paste invalid YAML → error. Submit with missing mapping → 400.
2. Existing `tests/integration/test_dashboards.py` import tests already cover API; no new backend tests required.

---

## YAML parsing on client

If the project has no client-side YAML parser, options: (a) add a small one (e.g. js-yaml via CDN or bundle); (b) accept JSON as well and use JSON.parse for that path; (c) minimal regex to extract `domains:` and list. Prefer (a) or (b) for robustness. Check frontend for existing dependencies.
