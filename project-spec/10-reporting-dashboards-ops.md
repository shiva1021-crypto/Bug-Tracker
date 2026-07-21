# Stage 10 — Reporting, Dashboards & Ops

## Goal
Surface insight (reports, dashboards) and make the app safe and ready to
actually deploy: email notifications, rate limiting, and production
hosting.

## Prerequisites
Stage 9 (extensibility) must be complete. This is the final stage.

## Features to build
**Reports**
- Filterable by date range, status, priority, and project (Admin/PM only).
- Charts: status breakdown, priority distribution, issues-by-category.
- CSV export of the filtered issue list — must be safe against CSV formula injection (neutralize values starting with `=`, `+`, `-`, `@`, or a tab character by prefixing them, e.g. with a leading apostrophe, before writing the export).
- Printer-friendly view.

**Configurable Dashboard**
- Grid of widgets the user can add/remove/resize (full, half, third width).
- Widget types: Statistics Summary, Recent Issues, Issues by Status (chart), Issues by Priority (chart), Issues by Severity (chart), Issues by Type (chart).
- New users get a sensible default layout automatically (e.g. Statistics Summary + Issues by Status + Issues by Priority + Recent Issues).

**Email Notifications**
- Sent for: issue assignment, status changes (to reporter + watchers), registration approval/rejection.
- Do not send emails synchronously inside the request/response cycle — write to an outbox table and process it with a background worker/thread so a slow SMTP server never blocks a user's page load.

**Rate Limiting**
- Limit login and registration attempts per IP/account to slow down brute-force attempts.
- Support both an in-memory backend (simplest, single-process) and a database-backed backend (works across multiple app instances) — configurable.

**Deployment**
- A production WSGI entry point (e.g. Waitress or Gunicorn) separate from the Flask dev server.
- Config split cleanly between development and production (see Stage 1's `APP_ENV` handling).
- A `Procfile` or equivalent for whichever hosting platform is being used.

## Frontend — Design & Layout

**Dashboard page** (`/dashboard`, the default landing page after login):
- CSS grid layout; each widget is a card with a header (title + a remove "×" button) and its content area.
- "+ Add Widget" button opens a modal: pick widget type, title, width — added widget appears immediately.
- Chart widgets render with Chart.js (loaded via CDN), doughnut style for the by-status/priority/severity/type breakdowns.

**Reports page** (`/reports`, Admin/PM only):
- Filter bar at top (date range, status, priority, project) with an "Apply" button.
- Below: bar charts for status and priority, a horizontal bar chart for category breakdown.
- "Export CSV" and "Print" buttons near the filter bar.
- A print-specific stylesheet rule (`@media print`) that hides the sidebar/header and filter controls, showing just the charts/data cleanly.

## Backend — Data Model & API

**Table: `dashboard_widgets`** — id, organization_id, user_id (nullable = org default), widget_type, title, config (JSON), position, width (enum: full/half/third).

**Table: `email_outbox`** — id, to_email, subject, body, status (enum: pending/sent/failed), created_at, sent_at.

**Table: `auth_rate_limits`** — id, identifier (IP or email), attempt_count, window_started_at (used only if `RATELIMIT_STORAGE=database`).

**Routes:**
| Method | Path | Purpose |
|---|---|---|
| GET | `/dashboard` | Render widget grid |
| POST | `/dashboard/widgets/add` | Add a widget |
| POST | `/dashboard/widgets/<id>/remove` | Remove a widget |
| GET | `/reports` | Filtered charts view |
| GET | `/reports/export.csv` | CSV download of filtered results |

**Background worker note:** run a simple loop/thread on app startup that polls `email_outbox` for `pending` rows, attempts SMTP delivery, and marks each `sent` or `failed`. Make it configurable to disable entirely (`NOTIFICATION_WORKER_ENABLED=false`) for environments without SMTP configured, so the app still runs without crashing.

## Definition of Done
- [ ] A CSV export containing a title like `=cmd|'/c calc'!A1` opens safely in Excel/Sheets as plain text, not as an executed formula.
- [ ] A new user's dashboard shows the default widget set with no manual setup.
- [ ] Removing and re-adding a widget preserves the rest of the layout.
- [ ] Repeated failed logins from the same IP eventually get blocked/delayed, and this resets after the configured window.
- [ ] The app starts and serves traffic via the production WSGI entry point, not just the dev server.
- [ ] Disabling the notification worker via config does not break issue creation/assignment/status changes — email just doesn't get sent.
