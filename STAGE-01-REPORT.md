# Stage 1 — Foundation & Setup · Completion Report

**Project:** Bug Tracker (Jira-style bug tracking & agile project management)
**Stage:** 1 of 10 — Foundation & Setup
**Spec:** `project-spec/01-foundation-setup.md`
**Status:** Complete and verified
**Date:** 21 July 2026

---

## 1. Goal of this stage

Stand up a runnable, empty skeleton: a Flask app that boots, connects to MySQL
through a **pooled** connection, and reports its own health. No product features —
this is pure plumbing that every later stage builds on.

Deliberately **not** built in Stage 1 (these belong to later stages):

- No database tables. The schema starts arriving in Stage 3.
- No HTML pages, templates, CSS or JS. First UI arrives in Stage 2.
- No authentication, sessions-in-use, CSRF, users, orgs, projects or issues.

The session cookie *settings* are configured now (HttpOnly, SameSite, Secure,
lifetime), because they are part of app configuration — but nothing writes to a
session yet.

---

## 2. What was built

### 2.1 Architecture & layering

The global convention from `project-spec/00-README.md` is enforced from this
stage onward:

```
routes/        HTTP handlers — parse request, return response. Thin.
   ↓
services/      Business rules — decide what a result means.
   ↓
repositories/  All SQL / direct database access lives here. Nothing else touches the DB.
   ↓
utils/         Cross-cutting helpers — the connection pool.
```

Routes never import a repository directly, and never talk to the database.
Even though Stage 1's only "query" is a `SELECT 1`, the full chain is wired so
later stages drop into an established pattern rather than inventing one.

The request path for `/health/db` demonstrates the whole stack:

```
GET /health/db
  → routes/health_routes.health_db()
      → services/health_service.db_status()
          → repositories/health_repository.ping()
              → utils/db.get_connection()   ← borrows from the pool
                  → SELECT 1
```

### 2.2 File inventory

| File | Layer | Purpose |
|---|---|---|
| `app.py` | app | Flask application factory; wires config, session settings, blueprints. Exposes module-level `app`. |
| `config.py` | config | Loads `.env`, exposes a single `Config` object, enforces the secret-key policy. |
| `run.py` | entry | Development server launcher (`python run.py`). |
| `wsgi.py` | entry | Production WSGI entry point for Waitress / Gunicorn. |
| `routes/health_routes.py` | routes | `GET /` and `GET /health/db` handlers on a `health` blueprint. |
| `services/health_service.py` | services | Builds the app-status payload; turns a DB ping result into a (payload, status-code) pair. |
| `repositories/health_repository.py` | repositories | `ping()` — opens a pooled connection, runs `SELECT 1`, closes it. |
| `utils/db.py` | utils | Lazily-created `MySQLConnectionPool` + `get_connection()` context manager. |
| `scripts/check_db.py` | scripts | Verifies MySQL is reachable; reports whether the app database exists. |
| `scripts/create_db.py` | scripts | Creates the database if missing (idempotent). |
| `.env.example` | config | Documented template for every supported environment variable. |
| `requirements.txt` | deps | Flask, mysql-connector-python, python-dotenv, waitress. |
| `.gitignore` | repo | Excludes `.env`, `.secret_key`, `__pycache__/`, venvs. |

Generated at runtime, never committed: `.env` (your local copy) and
`.secret_key` (the persisted dev session key).

---

## 3. Key design decisions

### 3.1 Connection pooling, not a long-lived connection

`utils/db.py` creates one `MySQLConnectionPool` per process, lazily on first
use, sized by `DB_POOL_SIZE`. Callers borrow a connection through a context
manager:

```python
with get_connection() as conn:
    ...
```

The `finally` block always calls `conn.close()`. On a *pooled* connection this
returns it to the pool rather than tearing down the socket — so a connection
can never leak, even if a query raises. The pool is created lazily (not at
import time) so the app can still boot and serve `/` when MySQL is down; only
`/health/db` fails.

### 3.2 Two separate health signals

The spec asks for a way to verify the database is reachable *separately* from
verifying the app is up. That is why there are two routes:

- `GET /` proves the Flask process is alive. It touches no database at all, so
  it stays 200 even when MySQL is down.
- `GET /health/db` proves MySQL is reachable through the pool.

This split matters operationally: a load balancer can use `/` for liveness
while a deeper monitor uses `/health/db` for readiness.

### 3.3 Clean 503, never a stack trace

`services/health_service.db_status()` wraps the ping in a broad `except` and
converts any failure into a structured payload plus HTTP 503:

```json
{ "status": "unavailable", "database": "bug_tracker_db", "error": "..." }
```

The client gets a readable message; no traceback escapes the process boundary.

### 3.4 Secret-key policy

Handled in `config._resolve_secret_key()`, and it differs by environment:

**Development** — if `SECRET_KEY` is empty, generate one with
`secrets.token_urlsafe(48)` and persist it to `.secret_key` on disk. Every
later boot reads that file back. This is what makes the key stable across
restarts (otherwise every restart would silently invalidate all sessions).

**Production** — the key must be supplied explicitly via the environment and
must be strong. The app **refuses to boot** if it is missing, shorter than 32
characters, or one of a blocklist of placeholder values (`changeme`, `secret`,
`dev`, `your-secret-key`, …). It raises a `ValueError` with a clear message that
includes the command to generate a proper key. There is no silent fallback to a
generated key in production — that would be the dangerous behaviour this rule
exists to prevent.

Because `config` is imported at the top of `app.py`, this check runs **before**
the app can bind a port or serve a single request. Failure is immediate and loud.

### 3.5 Configuration is environment-driven, never hardcoded

`config.py` loads `.env` via python-dotenv at import time and reads every value
from the environment, with typed helpers (`_bool_env`, `_int_env`) that fall
back to safe defaults rather than crashing on malformed input.

All ten variables named in the spec are supported:

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | `development` or `production`; drives the secret-key policy. |
| `SECRET_KEY` | *(auto in dev)* | Mandatory and strength-checked in production. |
| `DB_HOST` | `127.0.0.1` | |
| `DB_PORT` | `3306` | |
| `DB_USER` | `root` | |
| `DB_PASSWORD` | *(empty)* | |
| `DB_NAME` | `bug_tracker_db` | |
| `DB_POOL_SIZE` | `5` | Pool size passed to `MySQLConnectionPool`. |
| `SESSION_COOKIE_SECURE` | `false` | Set `true` behind HTTPS. |
| `SESSION_LIFETIME_SECONDS` | `28800` | 8 hours. |

`Config.db_connection_kwargs(include_database=False)` exists so the setup
scripts can connect to the MySQL *server* before the app's database exists —
the same credentials, minus the database name.

### 3.6 Session cookie hardening (configured now, used later)

`app.py` sets `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE="Lax"`,
`SESSION_COOKIE_SECURE` from config, and `PERMANENT_SESSION_LIFETIME` from
`SESSION_LIFETIME_SECONDS`. The security baseline in the README applies from
Stage 2 onward, but the cookie configuration is part of app setup, so it lands
here and is ready when Stage 2 introduces login.

---

## 4. Routes delivered

| Method | Path | Auth | Behaviour |
|---|---|---|---|
| GET | `/` | none | `200` JSON — `{"name":"Bug Tracker","stage":1,"status":"ok","environment":"development"}` |
| GET | `/health/db` | none | `200` when a pooled connection succeeds; `503` with a clean error message when it does not. |

---

## 5. Scripts & entry points

| Command | What it does |
|---|---|
| `python -m scripts.check_db` | Connects to the MySQL server (not the app DB), reports reachability, and says whether `bug_tracker_db` exists yet. Exit `0` / `1`. |
| `python -m scripts.create_db` | `CREATE DATABASE IF NOT EXISTS` with `utf8mb4` / `utf8mb4_unicode_ci`. Idempotent — safe to re-run. Creates **no tables**. |
| `python run.py` | Dev server on `127.0.0.1:5000` with debug/reload on. |
| `waitress-serve --port=8000 wsgi:app` | Production (cross-platform, incl. Windows). |
| `gunicorn --bind 0.0.0.0:8000 wsgi:app` | Production (Linux/macOS). |
| `python wsgi.py` | Production via Waitress directly. |

`check_db` and `create_db` both use a 5-second connection timeout so a wrong
host fails fast instead of hanging.

---

## 6. Setup & run procedure

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

copy .env.example .env            # Windows  (macOS/Linux: cp .env.example .env)
# edit .env → set DB_USER / DB_PASSWORD

python -m scripts.check_db        # confirm MySQL reachable
python -m scripts.create_db       # create bug_tracker_db

python run.py                     # → http://127.0.0.1:5000
```

---

## 7. Verification results

Each Definition-of-Done item was executed and observed.

| # | Requirement | Result |
|---|---|---|
| 1 | App starts with a single command and does not crash | **Pass** — `python run.py` boots cleanly. |
| 2 | `/` returns a 200 JSON response | **Pass** — `200 {"name":"Bug Tracker","stage":1,"status":"ok","environment":"development"}` |
| 3 | `/health/db` returns 200 when MySQL is up | **Pass** — `200 {"status":"ok","database":"bug_tracker_db"}` |
| 4 | `/health/db` returns a clean 503 (not a stack trace) when MySQL is down | **Pass** — `503 {"status":"unavailable","database":"bug_tracker_db","error":"2003 (HY000): Can't connect to MySQL server on '127.0.0.1:3306' (111)"}` |
| 5 | Restarting the app does not change the session secret key | **Pass** — key identical across two consecutive boots; persisted in `.secret_key`. |
| 6 | `APP_ENV=production` without a strong `SECRET_KEY` refuses to start | **Pass** — exits code `1` with `ValueError: Refusing to start in production: SECRET_KEY must be explicitly set to a strong value (at least 32 characters and not a default/placeholder)...` |
| 7 | Production boots normally *with* a strong key | **Pass** — control test; confirms the check rejects weak keys rather than blocking production outright. |

Additionally confirmed on the local Windows environment:

```
python -m scripts.check_db
  MySQL is reachable.
  Database 'bug_tracker_db' does NOT exist yet.

python -m scripts.create_db
  Database 'bug_tracker_db' is ready.
```

---

## 8. Notes for Stage 2

- The layering (`routes → services → repositories → utils`) and the pooled
  `get_connection()` context manager are the established patterns — new features
  should follow them rather than introducing new database access styles.
- `SECRET_KEY` is already wired into `app.config`, so Flask sessions will sign
  correctly the moment Stage 2 starts using them.
- Cookie hardening is already in place; Stage 2 adds CSRF tokens, password
  hashing, and server-side input validation on top.
- The database exists but is empty. The first tables arrive in Stage 3, when
  `organization_id` multi-tenancy is introduced.
