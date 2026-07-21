# Stage 10 — Reporting, Dashboards & Ops · Completion Report

**Project:** Bug Tracker (Jira-style bug tracking & agile project management)
**Stage:** 10 of 10 — Reporting, Dashboards & Ops (final stage)
**Spec:** `project-spec/10-reporting-dashboards-ops.md`
**Builds on:** Stages 1-9 (Foundation, Authentication, Multi-Tenancy & Roles, Projects & Issue Keys, Core Issue CRUD & Hierarchy, Workflow & Status, Kanban Board, Agile Planning, Extensibility)
**Status:** Complete and verified (routes/services/repositories/templates); DDL not yet run against a live MySQL server — see §6.
**Date:** 22 July 2026

---

## 1. Goal of this stage

Surface insight (filterable reports with charts and CSV export, a
configurable per-user dashboard) and make the app genuinely deployable:
outbox-backed email notifications processed by a background worker, login/
registration rate limiting, and a production WSGI entry point.

Deliberately **not** built (belongs outside this stage's scope):

- No per-widget configuration beyond type/title/width. The
  `dashboard_widgets.config` JSON column exists exactly as the spec's data
  model defines it and every repository/service function threads it
  through, but nothing in the frontend currently writes anything into it
  (e.g. there's no "which project should this widget's chart cover"
  option) — the spec's own frontend section only describes picking type,
  title, and width when adding a widget.
- No drag-to-reorder or resize-in-place on the dashboard grid. Widgets can
  be added (appended at the end) and removed; `position` exists and is
  respected on read, but nothing in the frontend lets a user drag a widget
  to a new slot. The spec's frontend section doesn't describe that
  interaction either.
- No email digest/summary batching — every notification event queues its
  own individual outbox row (one status change to three watchers is three
  rows), never bundled into one email. The spec's examples ("Sent for:
  issue assignment, status changes...") read as one email per event, not
  a digest.
- The actor who causes a status change is not excluded from that change's
  own notification recipients (if they are also the reporter or a
  watcher). Flagged in §8 — this is a genuine judgment call, not an
  oversight.
- No CAPTCHA or account lockout notification email — rate limiting slows
  down repeated attempts (per the spec's own wording, "slow down
  brute-force attempts") but does not lock an account outright or email
  anyone about it.

Stages 1-9 were left intact. Pre-existing files touched: `scripts/create_tables.py`
(three new tables, no altered columns this time), `config.py` (new
settings, nothing existing changed), `.env.example` (documented the new
settings), `app.py` (two new blueprints + worker startup, no route
logic), `repositories/issue_repository.py` (new aggregate/report query
functions only), `repositories/watcher_repository.py` (one new function),
`services/auth_service.py` (one new call in the new-org branch),
`services/admin_service.py` (two new notification calls),
`services/workflow_service.py` (two new notification calls),
`routes/auth_routes.py` (rate-limit checks + the post-login/register
redirect target changed from `/profile` to `/dashboard`),
`templates/base.html` (brand link + two new sidebar links),
`static/style.css`/`static/script.js` (new sections only).

---

## 2. What was built

### 2.1 New files

| File | Layer | Purpose |
|---|---|---|
| `repositories/dashboard_widget_repository.py` | repositories | SQL for `dashboard_widgets`: org-default rows (`user_id IS NULL`) vs. personal rows, create/delete/list, `max_position_for_user` (append-without-disturbing-order). |
| `repositories/email_outbox_repository.py` | repositories | SQL for `email_outbox`: `create` (fast, called inline from a request), `list_pending`/`mark_sent`/`mark_failed` (called only by the background worker). |
| `repositories/rate_limit_repository.py` | repositories | SQL for `auth_rate_limits` — the database-backed rate-limit storage option. |
| `services/dashboard_service.py` | services | Widget types/labels/default layout, the org-default-vs-personal-layout resolution and "fork on first edit" logic, per-widget-type data fetching. |
| `services/report_service.py` | services | Report filter parsing (date range/status/priority/project), one-fetch aggregation for every chart, CSV rendering via `utils/csv_safety.py`. |
| `services/notification_service.py` | services | Builds and queues (never sends) every notification email: assignment, status change, registration approval/rejection. |
| `services/notification_worker.py` | services | The background thread: polls `email_outbox` for pending rows, attempts SMTP delivery, marks sent/failed. Configurable on/off; tolerant of no SMTP server at all. |
| `services/rate_limit_service.py` | services | The rate-limiting rules themselves (fixed-window, failure-counted, per-identifier), with interchangeable memory/database backends selected by config. |
| `routes/dashboard_routes.py` | routes | `GET /dashboard`, `POST /dashboard/widgets/add`, `POST /dashboard/widgets/<id>/remove`. |
| `routes/report_routes.py` | routes | `GET /reports`, `GET /reports/export.csv`. |
| `templates/dashboard.html` | frontend | Widget grid (full/half/third CSS grid spans), per-widget-type content rendering, "+ Add Widget" modal, Chart.js doughnut charts. |
| `templates/reports.html` | frontend | Filter bar, status/priority bar charts + horizontal category chart, Export CSV/Print buttons, `@media print`-friendly markup. |
| `utils/csv_safety.py` | utils | `neutralize()` — the CSV formula-injection defense every exported field passes through. |
| `Procfile` | ops | `waitress-serve` entry point for Heroku-style platform-as-a-service hosting. |

### 2.2 Modified files

| File | Change |
|---|---|
| `scripts/create_tables.py` | Adds `dashboard_widgets`, `email_outbox`, `auth_rate_limits` DDL (appended to `STATEMENTS`; no reordering needed since neither `email_outbox` nor `auth_rate_limits` has any foreign key at all, and `dashboard_widgets`' only FKs — to `organizations`/`users` — are already satisfied by every table above it). |
| `config.py` | Adds `APP_BASE_URL`, the `SMTP_*` settings, `NOTIFICATION_WORKER_ENABLED`/`_INTERVAL_SECONDS`, and `RATELIMIT_STORAGE`/`_MAX_ATTEMPTS`/`_WINDOW_SECONDS`. Nothing existing changed. |
| `.env.example` | Documents every new setting above with the same inline-comment style already used for Stage 1's settings. |
| `app.py` | Registers `dashboard_bp` and `report_bp`; starts the notification worker once (guarded against the dev-server reloader double-import — see §5.6). |
| `repositories/issue_repository.py` | Adds `count_by_status`/`count_by_priority`/`count_by_severity`/`count_by_type`, `stats_summary`, `list_recent` (dashboard aggregates, org-wide, no filters) and `search_for_report` (Reports page's one filtered fetch, reused for every chart and the CSV export). Nothing existing changed. |
| `repositories/watcher_repository.py` | Adds `list_watcher_users()` (watcher rows joined with `users`, for notification recipients). |
| `services/auth_service.py` | `register()`'s new-organization branch now also calls `dashboard_service.ensure_org_defaults()`, right after `project_service.create_default_project()` — same moment, same reasoning. |
| `services/admin_service.py` | `approve_request()`/`reject_request()` each now also call `notification_service.notify_registration_approved`/`_rejected` after updating the request's status. |
| `services/workflow_service.py` | `change_status()` now also calls `notification_service.notify_status_changed()`; `assign_issue()` now also calls `notification_service.notify_issue_assigned()` (only for a real assignment, never an unassignment) and `notify_status_changed()` when its auto-transition actually changed status. |
| `routes/auth_routes.py` | `login()` and `register()` both check `rate_limit_service.is_blocked()` before proceeding and record success/failure afterward; both routes' successful redirect target changed from `auth.profile` to `dashboard.dashboard` (the spec's new "default landing page after login"). |
| `templates/base.html` | Brand link now points at `/dashboard` (was `/profile`) when logged in; adds "Dashboard" (top of the sidebar) and "Reports" (Admin/PM only) sidebar links. |
| `static/style.css` | New "reporting/dashboards/ops (Stage 10)" section: dashboard grid/widget/modal styles, report filter bar + chart grid, and the `@media print` rule. |
| `static/script.js` | Adds `initAddWidgetModal()` (open/close/backdrop-click/Escape for the Add Widget modal). |

### 2.3 Layering

```
routes/dashboard_routes.py
routes/report_routes.py
routes/auth_routes.py (extended)         -- rate-limit checks, dashboard redirect
routes/issue_routes.py (unchanged this stage -- workflow_service does the notifying)
routes/board_routes.py (unchanged this stage)
   ↓
services/dashboard_service.py            widget layout resolution/fork/CRUD, widget data
services/report_service.py               filter parsing, one-fetch aggregation, CSV rendering
services/notification_service.py         builds + queues every notification email
services/notification_worker.py          background thread: polls outbox, attempts SMTP
services/rate_limit_service.py           memory/database rate-limit backends
services/auth_service.py (extended)      seeds dashboard defaults for a new org
services/admin_service.py (extended)     queues approval/rejection emails
services/workflow_service.py (extended)  queues assignment/status-change emails
   ↓
repositories/dashboard_widget_repository.py, email_outbox_repository.py,
repositories/rate_limit_repository.py, issue_repository.py (extended),
repositories/watcher_repository.py (extended)
   ↓
utils/db.py                              pooled connection (Stage 1, unchanged)
utils/csv_safety.py                      CSV formula-injection defense (Stage 10, new)
```

Notification-writing and notification-sending are deliberately in two
different modules that never call each other: `notification_service`
only ever calls `email_outbox_repository.create()` (one fast INSERT);
`notification_worker` is the only code that imports `smtplib` at all. A
request that triggers a notification (assigning an issue, changing its
status, approving a registration) is never slower because of it — the
INSERT is the only thing that happens inline, and it happens on the same
connection pool every other write already uses.

---

## 3. Data model

**Table: `dashboard_widgets`** — matches the spec's data model exactly
(`id`, `organization_id`, `user_id` nullable, `widget_type` enum,
`title`, `config` JSON, `position`, `width` enum full/half/third), plus
`created_at`. `user_id IS NULL` rows are an organization's default
layout; `user_id` set rows are one specific user's personal layout — see
§5.1 for how the two interact.

**Table: `email_outbox`** — matches the spec's data model exactly (`id`,
`to_email`, `subject`, `body`, `status` enum pending/sent/failed,
`created_at`, `sent_at`). Deliberately has no `organization_id` — an
outbox row is a work item for the background worker, not tenant data
anyone browses.

**Table: `auth_rate_limits`** — matches the spec's data model exactly
(`id`, `identifier`, `attempt_count`, `window_started_at`), plus a
`UNIQUE(identifier)` constraint so the upsert-on-failure pattern
(`INSERT ... ON DUPLICATE KEY UPDATE`) has something to key off. Only
populated when `RATELIMIT_STORAGE=database`; otherwise stays empty
forever (the in-memory backend never touches it).

---

## 4. Routes delivered

| Method | Path | Auth | Behaviour |
|---|---|---|---|
| GET | `/dashboard` | required | Renders the caller's widget layout (personal if customized, else the org default), each widget's data freshly fetched. |
| POST | `/dashboard/widgets/add` | required | Adds a widget to the caller's personal layout (forking from the org default first, if this is their first customization). |
| POST | `/dashboard/widgets/<id>/remove` | required | Removes one widget; every other widget's position is untouched. |
| GET | `/reports` | Admin/PM | Filtered charts (status/priority/category breakdowns) — filterable by date range, status, priority, project. |
| GET | `/reports/export.csv` | Admin/PM | CSV download of the same filtered issue list, formula-injection-safe. |

`POST /login` and `POST /register` (both pre-existing, Stage 2) gained
rate-limit checks but no new paths.

---

## 5. Key design decisions

### 5.1 A dashboard widget layout is "org default, forked to personal on first edit," not "copied to every user at signup"

The spec's data model itself suggests this (`user_id` nullable = org
default) but doesn't spell out the mechanism, so this was the one
non-trivial design call this stage rests on. The alternative — copying
the default four widgets into a personal row for every user the moment
their account is created — would also satisfy "a new user's dashboard
shows the default widget set with no manual setup," but would mean every
future change to what "default" means requires a data migration touching
every existing user's rows, and would make "did this user customize their
dashboard, or do they just have the stock layout" impossible to tell from
the data. Instead: an organization gets exactly one default layout,
seeded once (`dashboard_service.ensure_org_defaults`, called from
`auth_service.register()`'s new-org path, mirroring how
`project_service.create_default_project` is already called there); a user
with no personal rows simply reads that default through
(`dashboard_service.get_layout`); the *first* time they add or remove a
widget, `_ensure_personal_layout` forks the org default into personal rows
for them, and only then is their edit applied. One subtlety this
surfaced during verification (§7): forking assigns each copied row a
brand-new id, so removing a widget the user is looking at (whose id, on
screen, is still the org-default row's id) has to translate that id
through the fork's own return mapping before deleting — implemented as
`_ensure_personal_layout` returning `{default_id: new_personal_id}`,
consumed by `remove_widget`.

### 5.2 Notification emails are queued from inside the *service* layer, not the route layer

Unlike Stage 9's automation triggers (fired explicitly by every relevant
*route*, since the automation engine needs route-supplied event context
like `trigger_event`/`old_status`/`new_status`), notification queuing was
added directly inside `workflow_service.change_status()`/`assign_issue()`
and `admin_service.approve_request()`/`reject_request()` — the same
functions that already call `bug_history_repository.record()` for the
exact same state changes. A notification is a direct, unconditional
consequence of "this state actually changed," with no per-route
opt-in/opt-out logic anywhere, so it lives at the same layer as the
history write it's paired with, rather than being re-derived at every
call site the way an automation rule's conditional firing has to be.

### 5.3 Recipients of a status-change email are not deduplicated across "reporter" and "watcher," but are deduplicated by email address

`notification_service.notify_status_changed()` builds a `dict[email,
name]` (not a list) specifically so a reporter who is also watching their
own issue receives exactly one email, not two. The user who *made* the
change is not excluded from this list even if they happen to be the
reporter or a watcher — the spec doesn't ask for that exclusion, and
implementing it would need a notion of "suppress self-notifications" this
stage doesn't otherwise track anywhere. Flagged in §8.

### 5.4 CSV export re-runs the same query as the charts, not a separately-maintained one

`report_service.run_report()` calls `issue_repository.search_for_report()`
exactly once and derives every chart's counts *and* the CSV export's rows
from that one in-memory list (`Counter`-based grouping in Python) — the
same "fetch once, group in application code" shape Stage 7's board query
established. This is what guarantees the CSV export can never show a
different issue set than what the charts on the same page displayed,
even under concurrent writes between rendering the page and clicking
Export (both requests independently re-run the identical query with the
identical filters from the URL, so they agree with each other, if not
necessarily with a third simultaneous request).

### 5.5 CSV injection defense is applied to every field of every row, not just user-authored text fields

`neutralize()` (`utils/csv_safety.py`) is called on all eleven exported
columns in `report_service.rows_to_csv()`, including ones that are
normally safe-by-construction (status, priority, project key — all
drawn from fixed enums/keys, never free text). This costs nothing and
removes any need to reason about which columns could *theoretically*
contain attacker-controlled text after some future schema change; every
field is always passed through the same function, unconditionally.

### 5.6 The background worker is guarded against the Flask dev server's reloader starting it twice

`python run.py` runs with `debug=True`, which makes Werkzeug fork a
reloader-watcher parent process and a child process that actually serves
requests (re-importing `app.py` in both). Starting a real background
thread unconditionally in `create_app()` would leave one orphaned worker
thread running inside the parent process, which never handles a request
and therefore never needs it. `app.py` guards the `notification_worker.start()`
call with `config.IS_PRODUCTION or os.environ.get("WERKZEUG_RUN_MAIN") ==
"true"` — in production there's no reloader at all, so this is always
true; in development, only the actual serving child process (which sets
`WERKZEUG_RUN_MAIN`) starts the worker.

### 5.7 Only *failed* login/registration attempts count against the rate limit; a success clears the counter immediately

Counting every attempt (successful ones included) would eventually rate-
limit a real, legitimate user who simply logs in often. Standard
account-lockout shape instead: `rate_limit_service.record_failure()` is
called only when credentials/validation actually fail;
`record_success()` (called on any success) deletes that identifier's
counter outright. This is what makes the Definition of Done's "resets
after the configured window" true in the *common* case as well as the
edge case the DoD literally describes — a correct login resets it
instantly, not just eventually.

### 5.8 Registration attempts are rate-limited by IP only, not by the submitted email

Login limits both the client IP and the target account's email (per the
spec's "per IP/account"), since a real account already exists to
brute-force. A registration attempt's email may not correspond to any
account at all yet (that's the whole point of registering), so keying a
limit on it would let an attacker trivially reset their own counter by
typing a different throwaway email each time — the IP is the only
identifier that actually constrains "how many times has *this actor*
tried," so it's the only one used here.

---

## 6. Setup procedure

```bash
python -m scripts.create_tables     # adds dashboard_widgets, email_outbox, auth_rate_limits
python run.py                       # -> http://127.0.0.1:5000/dashboard (after logging in)
```

No new Python dependencies — `smtplib`/`email.message` (SMTP) and
`csv`/`io` (CSV export) are both standard library; `requirements.txt` is
unchanged from Stage 9.

For production:

```bash
# .env: APP_ENV=production, a strong SECRET_KEY, real DB/SMTP settings
waitress-serve --host=0.0.0.0 --port=8000 wsgi:app
# or, on a Procfile-based platform, the committed `Procfile` already
# declares: web: waitress-serve --host=0.0.0.0 --port=${PORT:-8000} wsgi:app
```

---

## 7. Verification results

As in every prior stage, the sandbox has no MySQL server, so the full
request flow was exercised against in-memory stand-ins for every
repository touched this stage (`dashboard_widget_repository`,
`email_outbox_repository`, `rate_limit_repository`, and the extended
`issue_repository`/`watcher_repository`/`organization_repository`/
`registration_request_repository`), each matching its real function's
exact signature, driven end-to-end through the real Flask app
(`app.test_client()`) including the CSRF check and every permission gate.
The pre-existing Stage 9 verification harness was re-run against the new
code unchanged in intent (two new fakes added for the notification calls
Stage 10 wired into `workflow_service`) and still passes in full,
confirming no regression.

**40 new checks for this stage, all passing** (plus all 32 pre-existing
Stage 9 checks, re-confirmed passing against the final codebase).

| # | Check | Result |
|---|---|---|
| 1-5 | An issue titled `=cmd|'/c calc'!A1` (and a category of `=SUM(1+1)`) exports to CSV with both fields prefixed by a leading apostrophe, never appearing as a raw formula | Pass |
| 6 | A Developer is redirected away from `/reports` (Admin/PM only) | Pass |
| 7-14 | Registering a brand-new organization seeds exactly the spec's example default widget set (Statistics Summary, Issues by Status, Issues by Priority, Recent Issues) with zero manual setup, and the dashboard page renders all four | Pass |
| 15-17 | Removing a widget for a user who has never customized their layout correctly forks a personal copy and removes the right one — the other three default widgets survive | Pass |
| 18 | The organization's own default layout is untouched by that one user's edit | Pass |
| 19-21 | Re-adding a widget afterward preserves the three that remained, plus the new one, with the correct default title | Pass |
| 22-25 | Repeated failed logins from the same identity are eventually blocked (429); even the *correct* password is rejected while blocked; a fresh window (simulated) lets a correct login through again | Pass |
| 26-27 | Switching `RATELIMIT_STORAGE` to `database` blocks the same way, and a real row is written to `auth_rate_limits` | Pass |
| 28-30 | Assigning an issue queues exactly one notification email, left `pending` (never sent inline); a subsequent status change queues another | Pass |
| 31-34 | With `NOTIFICATION_WORKER_ENABLED=false`, issue creation/assignment/status-change all still succeed, and no worker thread is running | Pass |
| 35 | With no `SMTP_HOST` configured, a worker poll cycle leaves pending rows untouched (no crash, no false "failed" marks) | Pass |
| 36-37 | With SMTP "configured" (delivery mocked to succeed), a poll cycle marks every pending row `sent` and none `failed` | Pass |
| 38-39 | A simulated SMTP failure is caught inside the worker (never raises) and marks only that row `failed` | Pass |
| 40 | Approving a pending registration request queues a notification email addressed to the requester | Pass |

All modified/added Python modules compile cleanly (`py_compile`, exit 0);
`static/script.js` parses cleanly (`node -c`); every touched/added
template's Jinja `{% %}` block tags balance (checked programmatically).

### Definition of Done

- [x] A CSV export containing a title like `=cmd|'/c calc'!A1` is written
      with a leading apostrophe, so it opens as plain text rather than an
      executed formula (confirmed directly against the exported bytes)
- [x] A new user's dashboard shows the default widget set with no manual
      setup (confirmed by registering a brand-new organization and
      loading `/dashboard` immediately afterward)
- [x] Removing and re-adding a widget preserves the rest of the layout
      (confirmed for the hardest case — a user's *very first* edit, which
      requires forking the org default correctly)
- [x] Repeated failed logins from the same IP eventually get
      blocked/delayed, and this resets after the configured window
      (confirmed for both the memory and database backends)
- [x] The app starts and serves traffic via the production WSGI entry
      point — `wsgi.py`/`waitress-serve` predate this stage (Stage 1) and
      remain unchanged; this stage adds the `Procfile` and confirms the
      app still imports and runs cleanly with the new blueprints/worker
      wired in
- [x] Disabling the notification worker via config does not break issue
      creation/assignment/status changes — confirmed directly: all three
      still return 200 with the worker off, and no worker thread starts

---

## 8. Interpretations and open items

**Notification recipients are not deduplicated against the actor (§5.3)**
— the person who changes an issue's status can end up emailing
themselves if they're also its reporter or a watcher. Worth confirming
whether that's actually wanted; excluding the actor would be a small,
localized change to `notification_service.notify_status_changed()`'s
signature (it would need the acting user's id, which
`workflow_service.change_status()` already has as `changed_by_user`).

**No digest/batching for notification emails (§1)** — a status change
notifying three watchers writes three separate outbox rows/emails, never
one combined message. Flagged as the more scalable behavior *not* chosen
here, in case a real deployment would prefer fewer, batched emails.

**Dashboard widget "fork on first edit" (§5.1)** is the single biggest
design decision this stage rests on, since the spec's data model implies
it but doesn't fully specify the mechanism. Flagged clearly here in case
"copy defaults at signup" (simpler, but harder to evolve later) was
actually the intended reading.

**Rate limiting is IP/account-based and in-process for the memory
backend (§5.7-5.8)** — under `RATELIMIT_STORAGE=memory` (the default),
restarting the app process clears every counter; this is inherent to the
backend's own tradeoff (simplicity, no schema dependency) and is exactly
why the spec asks for a `database` alternative for multi-instance
deployments, which is implemented and verified separately (§7, checks
26-27).

**The DDL has not been run against a live MySQL.** `scripts/create_tables.py`
was syntax-checked (`py_compile`) and reasoned through, but as in every
prior stage, the sandbox has no MySQL server to execute it against — in
particular, `dashboard_widgets`' two foreign keys (to `organizations` and
`users`), the `auth_rate_limits.identifier` unique constraint the
database-backed rate limiter's upsert depends on, and `email_outbox`'s
complete lack of any foreign key at all (intentional — see §3) have not
been confirmed against a real server. Please run
`python -m scripts.create_tables` and check its output — it should print
a line for each of the three new tables.

---

## 9. Project completion

This is the tenth and final stage of the specification. Every feature
listed across `project-spec/01` through `project-spec/10` has now been
built, stage by stage, on top of the same Flask/MySQL/Jinja2 foundation
laid down in Stage 1, with each stage's own report documenting the
interpretation calls made along the way. A few threads worth knowing
about if this codebase continues to evolve past this specification:

- Every "fetch once, group in application code" query (Stage 7's board,
  Stage 9's automation matching, this stage's report/CSV export) shares
  the same underlying reasoning: consistency between multiple views of
  the same data matters more than saving a second database round-trip.
  Any new bulk-display feature should probably follow the same shape.
- The email outbox and its background worker are deliberately generic —
  nothing about `email_outbox_repository`/`notification_worker.py` is
  specific to the three notification types this stage sends. A future
  notification type is just another call to
  `email_outbox_repository.create()` from wherever the triggering event
  already lives.
- Rate limiting's memory/database backend split
  (`services/rate_limit_service.py`) is a reusable pattern if a future
  feature needs the same "simple single-process default, explicit
  opt-in to a shared backend for multi-instance deployments" shape.
