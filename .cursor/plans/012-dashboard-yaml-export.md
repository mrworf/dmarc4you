# Plan: Dashboard YAML export (Phase 4/6 — backend only)

## Goal

Implement **GET /api/v1/dashboards/{dashboard_id}/export**: return a portable YAML definition of the dashboard (name, description, domain names). Same access rule as get_dashboard: caller must have access to **all** dashboard domains; 403/404 otherwise. No import in this slice; export only. Content-Type `application/x-yaml` or `text/yaml`; body is YAML text.

## Why this slice

- Phase 4/6 call for “dashboard YAML import/export”. FRONTEND_AND_DASHBOARDS: “Export should serialize a portable dashboard definition without fixed environment-bound domain ids.” Small slice: one endpoint, reuse get_dashboard access logic, serialize to YAML.
- Enables portability and sets up for a future import slice (with domain remapping).

## Scope (in)

- **Dashboard service**: Add `export_dashboard_yaml(config, dashboard_id, current_user)` (or reuse get_dashboard and serialize in handler). Returns YAML string or None (not_found/forbidden). Portable shape: `name`, `description`, `domains` (list of domain **names**, not ids).
- **Handler**: `GET /api/v1/dashboards/{dashboard_id}/export`. Session required. Call service; if forbidden/not_found return 403/404; else return Response with body=YAML string, media_type=`application/x-yaml` (or `text/yaml`).
- **Docs**: Document GET .../export in API_V1.md (response: YAML with name, description, domains).
- **Tests**: Integration test: create dashboard, GET export as owner → 200, YAML contains name, description, domain names; GET as user without access to one domain → 403; GET non-existent → 404.

## Scope (out)

- POST /dashboards/import (domain remapping); UI for export/import; widget definitions in YAML.

---

## Files to create or edit

### Backend

| Path | Action |
|------|--------|
| `backend/services/dashboard_service.py` | Add `export_dashboard_yaml(config, dashboard_id, current_user)` → (yaml_str, None) on success or (None, "not_found"|"forbidden"). Reuse same access as get_dashboard; build dict `{name, description, domains: domain_names}`, serialize to YAML (e.g. `yaml.safe_dump`). |
| `backend/api/v1/handlers/dashboards.py` | Add `GET /{dashboard_id}/export`; call export_dashboard_yaml; return 200 with YAML body and Content-Type, or 403/404. |

### Docs

| Path | Action |
|------|--------|
| `docs/API_V1.md` | Document GET /api/v1/dashboards/{dashboard_id}/export: same auth as get dashboard; response YAML with name, description, domains (domain names). |

### Tests

| Path | Action |
|------|--------|
| `tests/integration/test_dashboards.py` | Add: export as owner → 200, YAML has name/description/domains; export as user without access → 403; export non-existent → 404. |

---

## Acceptance criteria

1. **GET /api/v1/dashboards/{dashboard_id}/export** with valid session and access to all dashboard domains: 200, body is YAML containing `name`, `description`, and `domains` (list of domain names). Content-Type indicates YAML.
2. **GET .../export** as user who lacks access to any dashboard domain: 403.
3. **GET .../export** with non-existent dashboard_id: 404.
4. Exported YAML uses domain **names** (not ids) so the definition is portable across environments.

---

## Tests and validation

1. **Integration**: Create dashboard (owner has access to domains), GET export → 200, parse YAML, assert name/description/domains match. As user without domain access, GET export → 403. GET export with bad id → 404.
2. **Run**: `pytest tests/` passes.

---

## YAML shape (example)

```yaml
name: My Dashboard
description: Optional description
domains:
  - example.com
  - other.com
```

Use `yaml.safe_dump` (PyYAML already used in config); keep keys explicit and order stable if needed.
