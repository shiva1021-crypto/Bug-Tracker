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

## Global conventions used across every stage

- **Backend:** Python 3.13+, Flask, MySQL 8+, `mysql-connector-python`, pooled connections.
- **Frontend:** Server-rendered Jinja2 templates, one shared `style.css` and `script.js`, no JS framework. Chart.js (via CDN) for charts.
- **Architecture layering:** `routes/` (HTTP handlers) → `repositories/` (SQL) → `services/` (business rules) → `utils/` (cross-cutting helpers). Keep this separation from Stage 1 onward.
- **Multi-tenancy:** every table that stores tenant data carries `organization_id`, and every query filters by it. Never trust a client-supplied ID without checking it belongs to the current organization.
- **Security baseline (apply from Stage 2 onward):** CSRF tokens on every POST form, hashed passwords, HttpOnly + SameSite session cookies, input validation server-side (never trust client-side validation alone).
- **Visual style:** clean, Jira-inspired UI — light sidebar + header layout, card-based content areas, a defined color system for priority/status badges, dark mode support from Stage 1's base layout onward.
