# Bug Tracker — Working Notes

Context for continuing this build in a new session. Read this first.

---

## What this project is

A Jira-style bug tracking and agile project management tool, built from scratch
against a written specification. Flask (Python) backend, MySQL, server-rendered
Jinja2 templates.

The full specification lives in `project-spec/` and is split into **10 stages**.
`project-spec/00-README.md` holds the global conventions; `01-` through `10-`
are the individual stage specs.

---

## Current state

| Stage | Name | Status |
|---|---|---|
| 1 | Foundation & Setup | **Done** — `STAGE-01-REPORT.md` |
| 2 | Authentication | **Done** — `STAGE-02-REPORT.md` |
| 3 | Multi-Tenancy & Roles | Not started — next |
| 4 | Projects & Issue Keys | Not started |
| 5 | Core Issue CRUD & Hierarchy | Not started |
| 6 | Workflow & Status | Not started |
| 7 | Kanban Board | Not started |
| 8 | Agile Planning | Not started |
| 9 | Extensibility | Not started |
| 10 | Reporting, Dashboards & Ops | Not started |

The app runs, connects to MySQL through a pooled connection, and supports
register / login / logout / profile with session auth.

---

## How the user wants this built — IMPORTANT

These rules have been given every stage. Follow them without being asked.

1. **One stage at a time.** Build only the stage requested.
2. **Do not read ahead.** Do not open other stage spec files, and do not add
   anything from a later stage — even if it seems obviously needed soon.
   Build *exactly* what the current stage describes, nothing more.
3. **Build on what exists.** Earlier stages are working. Extend them; never
   recreate or rewrite them. Touch prior files only where the new stage
   genuinely requires it, and say which ones changed.
4. **Files go in the project root** (`D:\Bug Tracker`), not in a subfolder.
5. **Never run git commands.** The user reviews, tests, then commits
   themselves. Do not run `git add`, `git commit`, or anything else in git.
6. **Finish with test instructions.** After building, explain exactly how the
   user can test it: commands to run, URLs to open, what they should see, and
   what failure/error cases should look like.
7. **Then write a stage report** when asked: `STAGE-0N-REPORT.md` in the project
   root. Follow the structure of the existing two — goal and explicit
   out-of-scope list, files, data model, routes, *design decisions with
   reasoning*, setup, verification results table, interpretations/open items,
   notes for the next stage.
8. **Flag interpretation calls and untested surfaces honestly.** Where a spec is
   ambiguous, pick the minimal reading, then say so explicitly rather than
   quietly expanding scope.

---

## Tech stack & conventions

From `project-spec/00-README.md`:

- Python 3.13+, Flask, MySQL 8+, `mysql-connector-python`, **pooled** connections.
- Server-rendered Jinja2. One shared `static/style.css` and `static/script.js`.
  No JS framework. Chart.js via CDN when charts are needed (Stage 10).
- **Layering — keep this strictly:**
  `routes/` (HTTP) → `services/` (business rules) → `repositories/` (SQL) →
  `utils/` (cross-cutting). Routes never touch the database directly.
- **Multi-tenancy (from Stage 3):** every tenant table carries
  `organization_id`, and every query filters by it. Never trust a client-supplied
  ID without verifying it belongs to the current organization.
- **Security baseline (Stage 2 onward):** CSRF on every POST form, hashed
  passwords, HttpOnly + SameSite cookies, server-side validation always.
- **Visual style:** Jira-inspired. Light sidebar + header, card-based content,
  defined color system for priority/status badges, dark mode support.

---

## Architecture as built

```
app.py                  factory; blueprints, global CSRF, no-store headers, template globals
config.py               .env loading, typed env helpers, secret-key policy
run.py / wsgi.py        dev launcher / production WSGI entry

routes/                 health_routes.py, auth_routes.py
services/               health_service.py, auth_service.py
repositories/           health_repository.py, user_repository.py
utils/                  db.py (pool), auth.py (session + login_required), security.py (CSRF)
scripts/                check_db.py, create_db.py, create_tables.py
templates/              base.html, partials/, auth/, errors/, profile.html
static/                 style.css, script.js
```

### Things already wired that later stages should reuse

- `utils/db.py::get_connection()` — context manager, borrows from the pool and
  always returns it. Use this for all DB access.
- `utils/auth.py::login_required` — the auth gate. `start_session()` is the
  single place session state is written, so `organization_id` and `role` go
  there in Stage 3.
- **CSRF is global** (`before_request` in `app.py`). New POST routes are
  protected automatically; the form just needs
  `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
- `current_user` and `csrf_token()` are injected into every template.
- `static/style.css` defines the design tokens (`--accent`, `--bg`, `--surface`,
  `--text`, `--danger`, …). **Use the variables, never literal hex** — dark mode
  is a variable swap and breaks if new CSS hardcodes colors.
- `scripts/create_tables.py` holds the DDL. Add new tables to its `STATEMENTS`
  list rather than creating a parallel script.

---

## Commands

```bash
# setup (already done on the user's machine)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # then set DB_USER / DB_PASSWORD

# database
python -m scripts.check_db      # is MySQL up? does the DB exist?
python -m scripts.create_db     # create the database
python -m scripts.create_tables # create/update tables

# run
python run.py                   # dev → http://127.0.0.1:5000
waitress-serve --port=8000 wsgi:app   # production
```

Key routes so far: `/` (JSON status), `/health/db`, `/register`, `/login`,
`POST /logout`, `/profile`.

---

## Environment notes

- User is on **Windows**, PowerShell, venv at `.venv`. Use Windows-style
  commands in instructions (`copy`, `.venv\Scripts\activate`).
- MySQL runs locally on `127.0.0.1:3306`, database `bug_tracker_db`.
- `.env` and `.secret_key` are gitignored and must never be committed. The dev
  secret key persists to `.secret_key`; production refuses to boot without a
  strong explicit `SECRET_KEY`.

### Sandbox limitations hit while building

- **The Linux sandbox has no MySQL server.** DB-backed flows were verified by
  monkeypatching the repository layer with an in-memory store. This works well —
  it exercises routes, services, CSRF, sessions and templates — but it means
  **DDL is never verified until the user runs it**. Always say so.
- The sandbox can create files in the mounted folder but **cannot delete them**
  (`Operation not permitted`). Don't create scratch files there; use `/tmp` or
  the outputs directory. A stray `.writetest` was left behind this way once.
- `pip install` in the sandbox can be slow/flaky on first run; packages cache
  afterwards.

---

## Decisions already made (don't silently reverse these)

- **`GET /` stays a JSON status endpoint.** Stage 1 defined that contract and no
  later stage has asked to change it. The header brand link points to `/profile`
  or `/login`, so users never land on it through the UI.
- **Login redirects to `/profile`.** Stage 2's DoD mentions a
  "landing/dashboard page" but defines no dashboard route, so `/profile` serves
  as the landing page. A real dashboard belongs to Stage 10.
- **Password hashing uses Werkzeug's `generate_password_hash` (scrypt).** Chosen
  because Werkzeug ships with Flask — no new dependency. `requirements.txt` is
  still just Flask, mysql-connector-python, python-dotenv, waitress.
- **Login failure is one code path.** `auth_service.authenticate()` returns
  `None` for both unknown-email and wrong-password so the route layer cannot leak
  the difference. Keep it that way.
- **Logout is POST-only** (405 on GET), to prevent forced-logout CSRF.
