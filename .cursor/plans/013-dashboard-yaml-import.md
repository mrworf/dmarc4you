# Plan: Dashboard YAML import with domain remapping (Phase 6)

## Goal

Implement **POST /api/v1/dashboards/import**: accept a portable dashboard YAML (or equivalent JSON) plus a **domain_remap** (YAML domain name → domain_id in this environment). Validate schema and importer access to all mapped domains; create a new dashboard owned by the current user. Same auth as create dashboard (session required; domain_ids must be in user's allowed set).

## Why this slice

- Phase 6 calls for "dashboard YAML import/export with domain remapping". Slice 012 delivered export only. This slice delivers import: one endpoint, reuse `create_dashboard` and `list_domains`/`can_create_dashboard_with_domains`, validate YAML shape and remap.
- FRONTEND_AND_DASHBOARDS: "require domain remapping", "validate importer access to mapped domains", "create a new dashboard owned by importer".

## Scope (in)

- **Dashboard service**: Add `import_dashboard_yaml(config, yaml_str, domain_remap, current_user)` (or accept a parsed dict + domain_remap). Parse YAML; validate `name` (non-empty), `description` (optional), `domains` (list of strings, non-empty). Resolve domain_ids via domain_remap; require every name in `domains` to have a remap entry; require all remapped domain_ids to be in the user's allowed set (reuse `list_domains` + `can_create_dashboard_with_domains`). Call `create_dashboard(config, name, description, domain_ids, owner_user_id=current_user["id"], current_user)`. Return `('ok', dashboard_dict)` or `('invalid', None)` (bad YAML/schema or missing remap) or `('forbidden', None)` (remap domain not allowed).
- **Handler**: `POST /api/v1/dashboards/import`. Request body JSON: `{ "yaml": "<string>", "domain_remap": { "<domain_name>": "<domain_id>", ... } }`. Session required. Register route **before** `/{dashboard_id}` so `import` is not captured as id. Return 201 with created dashboard; 400 for invalid YAML/schema or incomplete remap; 403 if any remapped domain not allowed.
- **Docs**: Document POST .../import in API_V1.md (request body, validation rules, 201/400/403).
- **Tests**: Integration tests: valid YAML + full remap → 201, dashboard has name/description/domain_ids; missing remap for a domain → 400; domain_id in remap not allowed to user → 403; invalid YAML or empty name/domains → 400.

## Scope (out)

- Widget definitions in YAML; UI for import (future slice); multipart file upload.

---

## Files to create or edit

### Backend

| Path | Action |
|------|--------|
| `backend/services/dashboard_service.py` | Add `import_dashboard_yaml(config, yaml_str, domain_remap, current_user)` → `('ok', dashboard_dict)` or `('invalid', None)` or `('forbidden', None)`. Parse YAML with `yaml.safe_load`; validate top-level keys `name`, `domains` (list of strings); require `domain_remap` to cover every name in `domains`; resolve `domain_ids`; check `can_create_dashboard_with_domains(domain_ids, allowed)`; call `create_dashboard(...)`. |
| `backend/api/v1/handlers/dashboards.py` | Add `POST /import` route **before** `GET /{dashboard_id}`. Pydantic body: `{ yaml: str, domain_remap: dict[str, str] }`. Call `import_dashboard_yaml`; return 201 with dashboard, or 400 (invalid), 403 (forbidden). |

### Docs

| Path | Action |
|------|--------|
| `docs/API_V1.md` | Document POST /api/v1/dashboards/import: body `{ "yaml": "...", "domain_remap": { "name": "domain_id", ... } }`; YAML shape as per export (name, description, domains); validation and 201/400/403. |

### Tests

| Path | Action |
|------|--------|
| `tests/integration/test_dashboards.py` | Add: import with valid YAML + complete domain_remap → 201, dashboard matches; missing key in domain_remap → 400; remap domain_id not allowed to user → 403; invalid YAML / empty name / empty domains → 400. |

---

## Acceptance criteria

1. **POST /api/v1/dashboards/import** with valid session, body `{ "yaml": "<export-shaped YAML>", "domain_remap": { "<name>": "<domain_id>", ... } }`: YAML parsed; name and domains validated; every domain name has a remap entry; all remapped domain_ids are in the user's allowed set; new dashboard created with that name, description, and domain_ids; owner = current user; 201 with created dashboard body.
2. **400** if YAML is invalid, or name is empty, or domains is empty or missing, or any domain name in YAML is missing from `domain_remap`, or `domain_remap` is not an object.
3. **403** if any `domain_id` in `domain_remap` is not in the current user's allowed domains (same rule as create_dashboard).
4. Route is registered so that `POST .../dashboards/import` is matched (not `import` as dashboard_id).

---

## Tests and validation

1. **Integration**: (a) Create two domains, login as admin, POST import with YAML `name: X, description: Y, domains: [example.com, other.com]` and domain_remap mapping both names to domain ids → 201, response has name X, description Y, domain_ids. (b) Same YAML, domain_remap omits one domain → 400. (c) domain_remap uses a domain_id the user is not allowed → 403. (d) Invalid YAML or empty name or empty domains → 400.
2. **Run**: `pytest tests/integration/test_dashboards.py` (and full `pytest tests/` if desired).

---

## YAML shape (same as export)

```yaml
name: My Dashboard
description: Optional description
domains:
  - example.com
  - other.com
```

`domain_remap` maps each string in `domains` to a `domain_id` valid in this environment; importer must have access to all those domain_ids.
