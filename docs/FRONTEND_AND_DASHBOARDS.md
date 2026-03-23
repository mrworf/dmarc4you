# Frontend and Dashboards

## Frontend approach

Use the Next.js frontend in `frontend-next/` as the canonical web UI.

Why this shape:

- shareable URLs
- responsive dashboard interactions
- easier drill-down without full page refreshes
- a dedicated frontend runtime that can be deployed separately from FastAPI or behind the same reverse proxy

## Route ideas

- `/login` (implemented)
- `/domains` (implemented)
- `/dashboards` (implemented)
- `/dashboards/:id` (implemented)
- `/search` (implemented)
- `/upload` (implemented)
- `/domain-maintenance-jobs/:id` (implemented)
- `/users` (implemented)
- `/apikeys` (implemented)
- `/audit` (implemented)

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

Dashboard detail `Results` owns the temporary controls for aggregate exploration:

- free-text search lives in the dashboard metadata card instead of its own toolbar card, with the label inline to the left of the input
- the `Results` header uses a `Range` control with quick presets that prefill the existing `from` / `to` date fields
- advanced controls open from a `Filters` action inside `Results`
- the `Filters` panel includes country filtering, grouping management, and include/exclude facet toggles
- active filter chips sit in the left side of the `Results` header directly beneath the title, while the range controls stay on a single row at the right on larger screens
- records-per-page lives beside the previous/next pagination controls in the `Results` footer
- dashboard detail also renders a `Trend` card directly above `Results`
- the chart always uses time on the X axis and a saved dashboard `chart_y_axis` setting on the Y axis
- the saved chart Y-axis is chosen only in dashboard create/edit forms, not from the live filter controls
- the chart summarizes SPF, DKIM, and DMARC outcomes together for the current dashboard filter scope and refreshes whenever the dashboard results scope changes
- the chart supports hover inspection, a larger modal view with persistent hover detail cards, and drag-to-select range updates that write back into the dashboard `from` / `to` filters

Dashboard aggregate tables also support a dashboard-only hover action menu:

- clicking a filterable value still performs the primary action immediately
- hovering long enough reveals `Include`, `Exclude`, and when applicable `Group`
- this hover menu is specific to dashboard `Live results`; the global search page keeps its existing interaction model

## Dashboard visible fields

- each dashboard persists an ordered `visible_columns` list for aggregate result tables
- owners and other eligible editors can change the saved visible fields
- editors can reorder saved fields directly in the dashboard edit flow; drag interactions should reflow the list live while dragging and must have a non-drag alternative such as move up/down controls
- aggregate dashboards and search can expose DMARC alignment columns (`dmarc_alignment`, `dkim_alignment`, `spf_alignment`) alongside raw SPF/DKIM results
- viewers inherit the saved column layout
- if no custom layout is stored, the backend applies a sensible DMARC analysis default

## Dashboard chart settings

- each dashboard persists a `chart_y_axis` setting
- supported Y-axis modes are `message_count`, `row_count`, and `report_count`
- the backend chart endpoint ignores pagination and table grouping so the visualization always reflects the underlying filtered record set over time
- temporary chart legend visibility and expanded-modal state are viewer-local UI state and are not saved with the dashboard definition

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
- responsive layouts that expand to use large desktop and ultrawide viewports without breaking smaller screens
- clear domain context in every view
- obvious archived/dormant states
- concise error messaging without oversharing sensitive internals
- good empty states for unconfigured domains / no data / archived domain effects

## Domain admin UX

- the Domains page should surface the latest maintenance status per visible domain
- eligible users can trigger a background `Recompute reports` action per domain
- recompute job detail lives on its own route instead of reusing the ingest-job views
