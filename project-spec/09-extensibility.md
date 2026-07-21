# Stage 9 — Extensibility

## Goal
Let each organization tailor the tool to its own needs without code
changes: custom fields, automation rules, time tracking, and release
versions.

## Prerequisites
Stage 8 (agile planning) must be complete.

## Features to build
**Custom Fields**
- Admin/PM can define project-specific fields: Text, Number, Date, Dropdown, Checkbox.
- Dropdown fields require at least 2 options. Fields can be marked required.
- Fields appear dynamically on the Add/Edit Issue form based on the selected project (load via AJAX when the project changes), and their values display on the issue detail sidebar.
- Deleting a field cascades to delete its stored values.

**Automation Rules**
- If-this-then-that rules that fire on issue events.
- Triggers: `issue_created`, `status_changed`, `field_updated`.
- Actions: `transition_status` (to a specific status), `assign_to` (specific user), `assign_to_role` (random user with a given role), `add_comment` (system comment, supports placeholders like `{issue_key}`).
- Optional conditions to restrict when a rule fires (field/operator/value, e.g. only when new status = "Testing").
- Rules can be scoped to one project or apply org-wide, and can be enabled/disabled without deleting them.

**Time Tracking**
- Log work entries on an issue: hours spent + description, recorded with user and timestamp.
- Track an original estimate and a remaining estimate per issue.
- Show total time spent (sum of entries), estimate, and remaining on the issue detail sidebar.

**Versions/Releases**
- Admin/PM can create versions per project: name, optional release date, status (`unreleased`/`released`/`archived`).
- Issues can be assigned a "fix version."
- Versions page shows issue counts per version (total/open/resolved); releasing a version marks it shipped, archiving hides it from the main list.

## Frontend — Design & Layout

**Project → Fields page** (`/projects/<id>/fields`, Admin/PM only):
- List of existing custom fields with type, required flag, and a delete button.
- "+ Add Field" form: Name, Type dropdown, conditionally-shown Options textarea (one per line) for Dropdown type, Required checkbox.

**Automation page** (`/automation`):
- List of rules as cards: name, trigger, condition summary, action summary, enabled toggle, edit/delete.
- "+ New Rule" form: Name, Trigger dropdown, dynamic condition builder (field/operator/value rows, add/remove), Action dropdown with action-specific fields (e.g. status picker for `transition_status`, user picker for `assign_to`), Scope (project or organization-wide).

**Issue Detail page (extend further):**
- Custom field values shown in the sidebar, grouped under a "Custom Fields" heading, using the same widget type they were defined with (text input display, dropdown as plain text, checkbox as ✓/✗).
- "Time Tracking" panel: Estimate / Spent / Remaining stats row, a "Log Time" mini-form (hours + description), and a chronological list of past entries below it.

**Versions page** (`/versions`):
- Table: Version name, release date, status badge, issue counts (open/resolved/total), Release/Archive action buttons.
- "+ New Version" form: Name, optional Release Date.

**Add/Edit Issue form (extend):** Fix Version dropdown, and custom fields rendered dynamically below the standard fields once a project is selected.

## Backend — Data Model & API

**Table: `custom_field_definitions`** — id, organization_id, project_id, name, field_type (enum: text/number/date/dropdown/checkbox), options (JSON, for dropdown), required (bool), display_order.

**Table: `custom_field_values`** — id, bug_id, field_id, value (text), unique on (bug_id, field_id).

**Table: `automation_rules`** — id, organization_id, project_id (nullable = org-wide), name, trigger_event (enum), conditions (JSON), actions (JSON), enabled (bool).

**Table: `time_entries`** — id, bug_id, user_id, hours_spent (decimal), description, logged_at.

**Alter `bugs`:** add `time_estimate DECIMAL(10,2) NULL`, `time_remaining DECIMAL(10,2) NULL`, `fix_version_id INT NULL` (FK → versions).

**Table: `versions`** — id, organization_id, project_id, name, description, release_date, status (enum: unreleased/released/archived). Unique on (project_id, name).

**Routes (grouped by feature):**
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/projects/<id>/fields` | Manage custom fields |
| GET | `/api/fields?project_id=` | JSON field list for dynamic form loading |
| GET/POST | `/automation` | List/create automation rules |
| POST | `/automation/<id>/toggle` | Enable/disable |
| POST | `/automation/<id>/delete` | Delete |
| POST | `/issues/<id>/time` | Log a time entry |
| POST | `/issues/<id>/estimate` | Update original/remaining estimate |
| GET/POST | `/versions` | List/create versions |
| POST | `/versions/<id>/release` | Mark released |
| POST | `/versions/<id>/archive` | Archive |

**Automation engine design note:** implement as a single function, e.g. `execute_automation_rules(organization_id, project_id, trigger_event, context)`, called at the end of every route that creates/changes an issue. It should: fetch enabled rules matching the org/project/trigger, evaluate each rule's conditions against the context, and run matching actions in order. Keep this decoupled from the route logic so new triggers/actions can be added without touching every route.

## Definition of Done
- [ ] Deleting a custom field definition removes its values from every issue that had one, without erroring.
- [ ] An automation rule with a condition (e.g. "only when new status = Testing") does not fire on unrelated status changes.
- [ ] `assign_to_role` picks a real user with that role in the org, not a hardcoded ID.
- [ ] Time spent total on the issue sidebar always equals the sum of its logged entries.
- [ ] Archiving a version hides it from the main Versions list but does not delete historical fix-version data on already-linked issues.
