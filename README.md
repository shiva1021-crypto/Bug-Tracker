# Bug Tracker

A Jira-style bug tracking and agile project management tool: multi-tenant
organizations, role-based permissions, issue hierarchy (Epic → Story/Task →
Subtask), a Kanban board, sprint planning with burndown charts, custom
fields, automation rules, configurable dashboards, and email notifications.

Built with Flask (Python) and MySQL, server-rendered with Jinja2 - no JS
framework, no build step.

## Tech stack

- Python 3.13+, Flask
- MySQL 8+, `mysql-connector-python` (pooled connections)
- Server-rendered Jinja2 templates, one shared `static/style.css` /
  `static/script.js`
- Chart.js (via CDN) for dashboard/report charts
- Waitress for production serving

## Prerequisites

- Python 3.13 or newer
- MySQL 8+ running locally (or reachable over the network)
- (Windows) PowerShell - the commands below use Windows syntax; substitute
  the usual `source .venv/bin/activate` / `cp` / `python -m` equivalents on
  macOS or Linux.

## Setup

```powershell
# 1. Clone/open the project, then create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy the example environment file and fill in your DB credentials
copy .env.example .env
notepad .env
```

At minimum, set `DB_USER` and `DB_PASSWORD` in `.env` to match your local
MySQL setup. Everything else has a sensible default for local development -
see `.env.example` for what each setting does (session cookie behavior,
SMTP/email, rate limiting, the background notification worker).

```powershell
# 4. Confirm MySQL is reachable
python -m scripts.check_db

# 5. Create the database, then create/migrate its tables
python -m scripts.create_db
python -m scripts.create_tables

# 6. (Optional) Seed realistic sample data - one organization with a login
#    for every role, two projects, sprints, issues, comments, and more.
#    See the printed output for the login emails/password.
python -m scripts.seed_dummy_data
```

`scripts/create_tables.py` is idempotent - safe to re-run any time after
pulling changes that touch the schema; it only creates or migrates what's
missing.

## Running the app

```powershell
# Development server (auto-reload, debug mode)
python run.py
```

Then open **http://127.0.0.1:5000**. A logged-out visitor sees the landing
page; Log In / Register from there. If you ran the seed script, log in with
one of the printed accounts - otherwise register a new account, which
creates a brand-new organization with you as its Admin.

```powershell
# Production server (Waitress)
waitress-serve --host=0.0.0.0 --port=8000 wsgi:app
```

Production mode requires `APP_ENV=production` and a strong, explicitly-set
`SECRET_KEY` (32+ characters, not a placeholder) in the environment - the
app refuses to boot otherwise. A `Procfile` is included for
platform-as-a-service hosts that read one.

## Project structure

```
app.py                  Flask app factory: blueprints, CSRF, session config
config.py               .env loading, typed settings, secret-key policy
run.py / wsgi.py         dev launcher / production WSGI entry point

routes/                  HTTP handlers only - parse request, call a service, render/redirect
services/                business rules, validation, permission checks
repositories/             all SQL lives here; routes and services never touch the DB directly
utils/                   cross-cutting helpers (db pool, auth/session, CSRF)
scripts/                  one-off setup scripts (create_db, create_tables, seed_dummy_data, check_db)

templates/                Jinja2 templates (one subfolder per feature area)
static/                   style.css, script.js (shared across the whole app)
uploads/                  issue screenshots (gitignored, not web-servable directly)

project-spec/             the original stage-by-stage specification this app was built from
STAGE-0N-REPORT.md        a written report for each of the 10 build stages
FEATURE-VERIFICATION-RESULTS.md   full checklist run confirming every feature works as specified
```

## Roles & permissions (quick reference)

| Action | Admin | Project Manager | Developer | Tester |
|---|---|---|---|---|
| Create projects, sprints, versions, custom fields, automation rules | ✅ | ✅ | ❌ | ❌ |
| Create issues | ✅ | ✅ | ✅ | ✅ |
| Edit any issue | ✅ | ✅ | own reports only | own reports only |
| Change issue status | ✅ | ✅ | assigned issues only | ❌ |
| Assign/reassign issues | ✅ | ✅ | ❌ | ❌ |
| View Reports, manage users | ✅ | Reports only | ❌ | ❌ |

Every table that stores tenant data is scoped by `organization_id`; users
in one organization can never see or act on another organization's data,
even by guessing an id in the URL.

## Testing

There's no automated test suite committed to the repo (the sandbox this
project was built in has no MySQL server, so verification during
development was done with fake in-memory repositories driving the real
Flask app - see each `STAGE-0N-REPORT.md`'s "Verification results" section
and `FEATURE-VERIFICATION-RESULTS.md` for what that covered).

To manually verify a running instance:

1. `python -m scripts.check_db` - confirms MySQL connectivity.
2. Register a new organization, confirm you land on `/dashboard` as its
   Admin with a default project and default dashboard widgets already
   there.
3. Create an issue, move it through statuses on the Kanban board, add a
   comment, watch it.
4. Visit `/reports` as Admin/PM and export a CSV.
5. See each `STAGE-0N-REPORT.md`'s own "How to test" section for the
   feature that stage introduced.

## Notes

- `.env` and `.secret_key` are gitignored and must never be committed.
- `uploads/` (issue screenshots) is gitignored - user-uploaded content,
  not source.
- The dev secret key auto-generates and persists to `.secret_key` on first
  run, so restarting the dev server doesn't log everyone out.
