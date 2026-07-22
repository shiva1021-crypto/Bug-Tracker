# Bug Tracker - Build-From-Scratch Specification

This folder contains a complete, stage-by-stage specification for building a
Jira-style bug tracking and agile project management tool from scratch: Flask
(Python) backend, MySQL database, server-rendered HTML/CSS/JS frontend.

## How to use this

Hand these documents to a developer (or an AI coding assistant) **one stage at
a time, in order**. Each document is self-contained: it lists what to build,
how it should look and how the backend/data should work, without assuming
access to any other codebase. Do not skip ahead - later stages assume the
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

## UI Reference (applied; source files removed)

Every template in `templates/`, plus `static/style.css` and
`static/script.js`, was hand-matched - structure, classes and wording - to
a reference UI design (real templates/CSS/JS from another app, used purely
as a visual design source, not reinvented or reinterpreted). That source
material lived in `reference-ui/` in this folder during development and has
since been removed now that its content is fully reflected in the real
app; the mapping table below is kept for reference on which page's design
came from which stage. See each `STAGE-0N-REPORT.md` in the project root
for the specific places a page's real data model didn't support something
the reference design assumed and what was done instead.

| Stage | Reference templates cloned |
|---|---|
| 2 - Authentication | `base.html`, `index.html`, `login.html`, `register.html`, `profile.html` |
| 3 - Multi-Tenancy & Roles | `users.html` |
| 4 - Projects & Issue Keys | `projects.html` |
| 5 - Core Issue CRUD & Hierarchy | `add_bug.html`, `edit_bug.html`, `bug_details.html`, `macros.html`, `view_bugs.html` |
| 6 - Workflow & Status | `bug_details.html` (comments/history/watch sections) |
| 7 - Kanban Board | `board.html` |
| 8 - Agile Planning | `backlog.html`, `view_bugs.html` (saved filter chips), `bug_details.html` (linked issues panel) |
| 9 - Extensibility | `project_custom_fields.html`, `automation_rules.html`, `versions.html`, `bug_details.html` (custom fields + time tracking panels) |
| 10 - Reporting, Dashboards & Ops | `dashboard.html`, `reports.html`, `database_error.html` |

Each stage document's "Frontend - Design & Layout" section repeats which
exact reference file(s) apply to it, so you don't have to keep flipping
back to this table.

## Global conventions used across every stage

- **Backend:** Python 3.13+, Flask, MySQL 8+, `mysql-connector-python`, pooled connections.
- **Frontend:** Server-rendered Jinja2 templates, one shared `style.css` and `script.js`, no JS framework. Chart.js (via CDN) for charts.
- **Architecture layering:** `routes/` (HTTP handlers) → `repositories/` (SQL) → `services/` (business rules) → `utils/` (cross-cutting helpers). Keep this separation from Stage 1 onward.
- **Multi-tenancy:** every table that stores tenant data carries `organization_id` and every query filters by it. Never trust a client-supplied ID without checking it belongs to the current organization.
- **Security baseline (apply from Stage 2 onward):** CSRF tokens on every POST form, hashed passwords, HttpOnly + SameSite session cookies, input validation server-side (never trust client-side validation alone).
- **Visual style:** clean, Jira-inspired UI - light sidebar + header layout, card-based content areas, a defined color system for priority/status badges, dark mode support from Stage 1's base layout onward.