# Stage 1 - Foundation & Setup

## Goal
Stand up a runnable, empty skeleton: a Flask app that boots, connects to
MySQL through a pooled connection, and reports its own health. No features
yet - this is pure plumbing everything else builds on.

## Prerequisites
None. This is the first stage.

## Features to build
- App boots locally with one command.
- App can connect to MySQL through a connection pool (not a single long-lived connection).
- A way to verify the database is reachable, separate from verifying the app itself is up.
- Environment-based configuration (dev vs production), loaded from a `.env` file, never hardcoded.
- A secret key for session signing that is auto-generated and persisted for local dev, but **must** be explicitly and strongly set in production (refuse to boot in production with a weak/default key).

## Frontend - Design & Layout
None yet. If you want a visible placeholder, a single JSON status response is enough - no HTML pages until Stage 2.

## Backend - Data Model & API

**Database:** create one empty database (name it whatever you like, e.g. `bug_tracker_db`). No tables in this stage - the schema starts arriving in Stage 3.

**Routes:**
| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Returns basic app status (name, stage, status). No auth. |
| GET | `/health/db` | Attempts to open and close a pooled DB connection; returns 200 if reachable, 503 with an error message if not. No auth. |

**Config values to support via environment variables:**
`APP_ENV` (development/production), `SECRET_KEY`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_POOL_SIZE`, `SESSION_COOKIE_SECURE`, `SESSION_LIFETIME_SECONDS`.

**Scripts to provide:**
- A script to verify MySQL is reachable and report whether the app's database exists yet.
- A script to create the database if it doesn't exist.
- A dev server launcher and a production WSGI entry point (e.g. via Waitress or Gunicorn).

## Definition of Done
- [ ] App starts with a single command and does not crash.
- [ ] `/` returns a 200 JSON response.
- [ ] `/health/db` returns 200 when MySQL is up, and a clean 503 (not a stack trace) when it's down.
- [ ] Restarting the app does not change the session secret key (dev mode persists it to disk).
- [ ] Setting `APP_ENV=production` without a strong `SECRET_KEY` causes the app to refuse to start, with a clear error message.
