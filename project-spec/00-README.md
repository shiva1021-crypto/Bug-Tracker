# Bug Tracker — Build-From-Scratch Specification

This folder contains a complete, stage-by-stage specification for building a
Jira-style bug tracking and agile project management tool from scratch: Flask
(Python) backend, MySQL database, server-rendered HTML/CSS/JS frontend.

## How to use this

Hand these documents to a developer (or an AI coding assistant) **one stage at
a time, in order**. Each document is self-contained: it lists what to build,
how it should look, and how the backend/data should work, without assuming
access to any other codebase. Do not skip ahead — later stages assume the
data model and routes from earlier stages already exist.

## Stage order

| # | Stage | File |
|---|---|---|
| 1 | Foundation & Setup | `01-foundation-setup.md` |
| 2 | Authentication | `02-authentication.md` |
| 3 | Multi-Tenancy & Roles | `03-multi-tenancy-roles.md` |
| 4 | Projects & Issue Keys | `04-projects-issue-keys.md` |
| 5 | Core Issue CRUD & Hierarchy | `05-core-issue-crud-hierarchy.md` |
| 6 | Workflow & Status | `06-workflow-status.md` |
| 7 | Kanban Board | `07-kanban-board.md` |
| 8 | Agile Planning | `08-agile-planning.md` |
| 9 | Extensibility | `09-extensibility.md` |
| 10 | Reporting, Dashboards & Ops | `10-reporting-dashboards-ops.md` |

## UI Reference (use this, don't reinvent the design)

`reference-ui/` in this folder contains the **actual, real source files** of
the original app's UI — every template, the full CSS, and the full JS,
copied as-is. This is not a description of the design, it *is* the design.

**Rule: when a stage's document says "use reference-ui/templates/X.html,"
copy that file's structure, classes, and wording directly into the new
project.** Only change what genuinely must change for the new stage's data
(variable names, route names, which fields exist yet). Do not redesign,
simplify, "improve," or reinterpret the layout, spacing, colors, icons, or
wording — the goal is a visual clone, not a reimagining.

- `reference-ui/static/css/style.css` — the entire shared stylesheet. Copy it in full starting at Stage 2 and never rewrite it; add to it only if a later stage introduces a component with no existing styles to reuse.
- `reference-ui/static/js/script.js` — the entire shared script (theme toggle, sidebar collapse, drag-and-drop, AJAX helpers). Copy it in full starting at Stage 2; extend it only when a stage needs new client-side behavior not already covered.
- `reference-ui/templates/*.html` — one file per page. See the mapping table below for which file belongs to which stage.

| Stage | Reference templates to clone |
|---|---|
| 2 — Authentication | `base.html`, `index.html`, `login.html`, `register.html`, `profile.html` |
| 3 — Multi-Tenancy & Roles | `users.html` |
| 4 — Projects & Issue Keys | `projects.html` |
| 5 — Core Issue CRUD & Hierarchy | `add_bug.html`, `edit_bug.html`, `bug_details.html`, `macros.html`, `view_bugs.html` |
| 6 — Workflow & Status | `bug_details.html` (comments/history/watch sections) |
| 7 — Kanban Board | `board.html` |
| 8 — Agile Planning | `backlog.html`, `view_bugs.html` (saved filter chips), `bug_details.html` (linked issues panel) |
| 9 — Extensibility | `project_custom_fields.html`, `automation_rules.html`, `versions.html`, `bug_details.html` (custom fields + time tracking panels) |
| 10 — Reporting, Dashboards & Ops | `dashboard.html`, `reports.html`, `database_error.html` |

Each stage document's "Frontend — Design & Layout" section repeats which
exact reference file(s) apply to it, so you don't have to keep flipping
back to this table.

## Global conventions used across every stage

- **Backend:** Python 3.13+, Flask, MySQL 8+, `mysql-connector-python`, pooled connections.
- **Frontend:** Server-rendered Jinja2 templates, one shared `style.css` and `script.js`, no JS framework. Chart.js (via CDN) for charts.
- **Architecture layering:** `routes/` (HTTP handlers) → `repositories/` (SQL) → `services/` (business rules) → `utils/` (cross-cutting helpers). Keep this separation from Stage 1 onward.
- **Multi-tenancy:** every table that stores tenant data carries `organization_id`, and every query filters by it. Never trust a client-supplied ID without checking it belongs to the current organization.
- **Security baseline (apply from Stage 2 onward):** CSRF tokens on every POST form, hashed passwords, HttpOnly + SameSite session cookies, input validation server-side (never trust client-side validation alone).
- **Visual style:** clean, Jira-inspired UI — light sidebar + header layout, card-based content areas, a defined color system for priority/status badges, dark mode support from Stage 1's base layout onward.
