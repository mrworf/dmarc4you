# Frontend and Dashboards

## Frontend approach

Use a plain HTML/CSS/JavaScript SPA with client-side routing and backend-served assets.

Why this shape:

- shareable URLs
- responsive dashboard interactions
- easier drill-down without full page refreshes
- no framework required unless the project later proves it beneficial

## Route ideas

- `/login` (implemented)
- `/app` (implemented)
- `/app/dashboards` (implemented)
- `/app/dashboards/:id` (implemented)
- `/app/search` (implemented)
- `/app/upload` (implemented)
- `/app/domains` (implemented)
- `/app/users` (implemented)
- `/app/apikeys` (implemented)
- `/app/audit` (implemented)

## URL-state requirements

Dashboard and search URLs should be bookmarkable and may include:

- dashboard id
- selected domains
- from/to timespan
- date preset-derived from/to values
- aggregate grouping mode for dashboard detail views
- widget focus or drill-down state
- include/exclude filters
- sort order and pagination when useful

The URL represents view state only. Authorization still lives on the backend.

## Dashboard rules

- each dashboard has one owner
- sharing is per-user only
- access levels: `viewer`, `manager`
- creator becomes owner
- viewer can never own
- manager may assign other viewers/managers if allowed
- dashboard assignment requires access to all dashboard domains

## Scope edit behavior

When editing dashboard domains, the UI must preflight the change.

If some assigned users would lose eligibility:

- warn before save
- show impacted users
- offer:
  - continue and remove invalid users
  - cancel and keep current dashboard unchanged

If the owner would become invalid, the UI must require ownership resolution before save.

## Viewer behavior

- may interact with filters temporarily
- may switch temporary aggregate grouping on dashboard detail pages
- may use bookmarks
- may not save dashboard settings or personal derived views

## Aggregate dashboard filtering

Dashboard detail pages support temporary aggregate grouping by:

- record date
- source IP
- resolved hostname
- resolved hostname domain

Grouping is URL-state only in v1 and is not saved with the dashboard definition.

## Dashboard visible fields

- each dashboard persists an ordered `visible_columns` list for aggregate result tables
- owners and other eligible editors can change the saved visible fields
- viewers inherit the saved column layout
- if no custom layout is stored, the backend applies a sensible DMARC analysis default

## Manager behavior

Managers can:

- create dashboards
- edit dashboards they manage
- rename them
- share them with viewers/managers
- delete only if they are the owner

## YAML import/export

Export should serialize a portable dashboard definition without fixed environment-bound domain ids. The dashboard detail view includes an **Export** action that downloads the current dashboard as portable YAML (same format as the export API).

Portable YAML also includes the saved `visible_columns` list.

Import flow:

1. upload YAML (paste in Import dashboard form on the dashboards page)
2. validate schema (client parses; invalid YAML shows an error)
3. detect logical domain placeholders (domains list from YAML)
4. require domain remapping (one dropdown per YAML domain → select local domain)
5. validate importer access to mapped domains (API returns 403 if not allowed)
6. create a new dashboard owned by importer (POST /api/v1/dashboards/import)

## UI design goals

- fast filtering and drill-down
- clear domain context in every view
- obvious archived/dormant states
- concise error messaging without oversharing sensitive internals
- good empty states for unconfigured domains / no data / archived domain effects
