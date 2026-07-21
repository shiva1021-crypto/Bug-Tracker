# Stage 2 — Authentication · Completion Report

**Project:** Bug Tracker (Jira-style bug tracking & agile project management)
**Stage:** 2 of 10 — Authentication
**Spec:** `project-spec/02-authentication.md`
**Builds on:** Stage 1 (Foundation & Setup) — see `STAGE-01-REPORT.md`
**Status:** Complete and verified
**Date:** 21 July 2026

---

## 1. Goal of this stage

Let a person create an account and log in and out securely. No roles or
organizations yet — the question this stage answers is only *"does this login
work, and is the session safe."*

Deliberately **not** built (each belongs to a later stage or was never asked for):

- No roles, permissions, or organizations — those arrive in Stage 3, along with
  `organization_id` and `role` in the session.
- No projects, issues, boards or dashboards.
- No password reset, email verification, "remember me", account lockout, or
  rate limiting — the spec does not list them, so they were not added.
- No user-editable profile. The profile page is read-only, exactly as specified
  ("Basic profile page showing the logged-in user's name and email").

Stage 1 was left intact. `app.py` is the only pre-existing file that changed,
and `/` and `/health/db` behave exactly as before.

---

## 2. What was built

### 2.1 New files

| File | Layer | Purpose |
|---|---|---|
| `scripts/create_tables.py` | scripts | Idempotent DDL for the `users` table. |
| `repositories/user_repository.py` | repositories | All SQL touching `users`. |
| `services/auth_service.py` | services | Validation, password hashing, authentication. |
| `utils/security.py` | utils | CSRF token generation, rotation, validation. |
| `utils/auth.py` | utils | Session start/end, `current_user()`, `login_required`. |
| `routes/auth_routes.py` | routes | `/register`, `/login`, `/logout`, `/profile`. |
| `templates/base.html` | frontend | Shared layout + header (used by every page from here on). |
| `templates/auth/login.html` | frontend | Centered login card. |
| `templates/auth/register.html` | frontend | Centered registration card. |
| `templates/profile.html` | frontend | Read-only profile. |
| `templates/partials/flashes.html` | frontend | Flash message area. |
| `templates/errors/400.html` | frontend | Shown when a CSRF token is missing/stale. |
| `static/style.css` | frontend | Shared palette, typography, components, dark mode. |
| `static/script.js` | frontend | User-menu dropdown + password-match check. |

### 2.2 Modified files

**`app.py`** — the only Stage 1 file touched. Four additions:

1. Registers `auth_bp` alongside the existing `health_bp`.
2. `before_request` — validates the CSRF token on every state-changing request.
3. `after_request` — sets `Cache-Control: no-store` on non-static responses.
4. `context_processor` — injects `current_user` and `csrf_token()` into every
   template.

### 2.3 Layering

The Stage 1 chain is followed exactly; no new patterns were introduced:

```
routes/auth_routes.py       reads the form, redirects or renders
   ↓
services/auth_service.py    validation, hashing, authentication decisions
   ↓
repositories/user_repository.py   the only module that writes SQL for users
   ↓
utils/db.py                 pooled connection from Stage 1 (unchanged)
```

`utils/auth.py` and `utils/security.py` sit beside `utils/db.py` as
cross-cutting helpers — they are imported by routes and by `app.py`, but they
never touch the database.

---

## 3. Data model

**Table: `users`** — created by `python -m scripts.create_tables`.

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK AUTO_INCREMENT | |
| `full_name` | VARCHAR(150) | NOT NULL |
| `email` | VARCHAR(150) | UNIQUE, NOT NULL |
| `password_hash` | VARCHAR(255) | NOT NULL |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP |

`ENGINE=InnoDB`, `utf8mb4` / `utf8mb4_unicode_ci`, matching the database
created in Stage 1. The DDL uses `CREATE TABLE IF NOT EXISTS`, so the script is
safe to re-run.

The `UNIQUE` constraint on `email` is the real guarantee against duplicate
accounts. The service layer also checks with `email_exists()` to produce a
friendly message, but the constraint is what actually enforces it — the check
alone would be racy under concurrent signups.

---

## 4. Routes delivered

| Method | Path | Auth | Behaviour |
|---|---|---|---|
| GET | `/register` | none | Renders the registration card. |
| POST | `/register` | none | Validates; on success creates the user and redirects to `/login`. On failure re-renders with flashes, HTTP 400. |
| GET | `/login` | none | Renders the login card. |
| POST | `/login` | none | On success starts the session and redirects to `/profile`. On failure re-renders with the generic error, HTTP 401. |
| POST | `/logout` | none | Clears the session, redirects to `/login`. **POST only** — `GET /logout` returns 405. |
| GET | `/profile` | **required** | Shows the logged-in user's name, email and join date. |

Stage 1's `GET /` and `GET /health/db` are unchanged.

**Session contents on login:** `user_id` and `full_name`, as specified.
(`organization_id` and `role` are added in Stage 3.)

---

## 5. Key design decisions

### 5.1 Password hashing without a new dependency

Passwords are hashed with Werkzeug's `generate_password_hash`, which defaults to
**scrypt** (`scrypt:32768:8:1$...`) and embeds a per-password random salt in the
output. Verification uses `check_password_hash`.

Werkzeug is already installed as a hard dependency of Flask, so this adds no new
package. `requirements.txt` is unchanged from Stage 1.

Plaintext passwords never leave the service layer: `user_repository.create()`
receives an already-hashed string, and a failed registration re-renders the form
with the name and email preserved but the password fields deliberately blank.

### 5.2 Login failures are indistinguishable

`auth_service.authenticate()` returns `None` for *both* "no such email" and
"wrong password". A single return value means the route layer physically cannot
tell the two cases apart, so it cannot leak the difference even by accident.
Every failure flashes the same constant, `GENERIC_LOGIN_ERROR`:

> Invalid email or password.

This was verified by diffing the two response bodies (see §7). They are
byte-identical apart from the per-session CSRF token and the email the user
typed back into the form — neither of which reveals whether the account exists.

`user_repository.get_by_id()` deliberately does not select `password_hash`; only
`get_by_email()` does, because only the login path needs it.

### 5.3 CSRF enforced centrally, not per-route

The README's security baseline requires CSRF tokens on every POST form from this
stage onward. Rather than decorating each route, `app.py` validates the token in
a `before_request` hook covering `POST`, `PUT`, `PATCH` and `DELETE`.

The consequence matters for later stages: a new POST route added in Stage 4 or 7
is protected by default, and *forgetting* the token breaks the form loudly
instead of silently leaving a hole.

Tokens are compared with `secrets.compare_digest` to avoid timing leaks, and are
rotated whenever the privilege level changes (login and logout).

### 5.4 Logout is POST-only

`GET /logout` returns **405 Method Not Allowed**. A logout reachable by GET can
be triggered by any third-party page embedding `<img src=".../logout">`, letting
an attacker forcibly log users out. The header's Log Out control is therefore a
real `<form method="post">` carrying a CSRF token, styled to look like a menu
item.

### 5.5 Session handling on login and logout

`start_session()` calls `session.clear()` *before* writing `user_id`, so nothing
from the anonymous session survives the privilege change, and rotates the CSRF
token — the standard defence against session-fixation. `end_session()` clears
and re-issues in the same way.

`session.permanent = True` opts the session into Stage 1's
`PERMANENT_SESSION_LIFETIME`, so `SESSION_LIFETIME_SECONDS` from `.env` actually
governs expiry.

### 5.6 The back button must not reveal protected pages

Clearing the session is not enough on its own: browsers will happily re-display
a cached HTML page when the user presses Back, without asking the server. The
`after_request` hook therefore sets `Cache-Control: no-store, no-cache,
must-revalidate, max-age=0` (plus legacy `Pragma`/`Expires`) on every non-static
response, forcing a fresh request that then redirects to `/login`.

Static assets are excluded so CSS and JS can still be cached normally.

### 5.7 Client-side validation is convenience, never trust

`script.js` shows a live "Passwords do not match" message and blocks submit. The
server re-checks the same rule, plus every other rule, in
`auth_service.validate_registration()`:

- full name present, ≤ 150 characters
- email present, ≤ 150 characters, matches a basic format pattern
- password present, ≥ 8 characters
- password and confirmation identical
- email not already registered

Emails are normalised (trimmed, lowercased) on both registration and login, so
`Ada@Example.com` and `ada@example.com` are the same account.

### 5.8 Visual foundation

Per the spec, this stage establishes the design system every later stage
inherits — all of it in `static/style.css` as CSS variables:

| Token | Light | Purpose |
|---|---|---|
| `--accent` | `#0052cc` | Primary actions, links, focus rings |
| `--bg` | `#f4f5f7` | Page background |
| `--surface` | `#ffffff` | Cards, header |
| `--border` | `#dfe1e6` | Dividers, input borders |
| `--text` / `--text-muted` | `#172b4d` / `#6b778c` | Body / secondary text |
| `--danger` / `--success` | `#de350b` / `#006644` | Error and success states |

Typography is a clean system sans-serif stack (`--font-ui`), with a monospace
stack (`--font-mono`) reserved for the logo mark and, later, issue keys.

**Dark mode** works by overriding those variables inside a
`@media (prefers-color-scheme: dark)` block. Because every rule references
variables rather than literal colors, dark mode required no duplicate component
CSS and later stages get it for free as long as they keep using the tokens.

The base layout provides the header specified: brand on the left; when logged in,
an avatar + name button opening a dropdown with Profile and Log Out; when logged
out, Log In and Register links.

---

## 6. Setup procedure

Assuming Stage 1 is already set up (venv, `.env`, database created):

```bash
python -m scripts.create_tables     # creates the users table
python run.py                       # → http://127.0.0.1:5000
```

`requirements.txt` did not change — no new packages are needed for this stage.

---

## 7. Verification results

Because the sandbox used for development has no MySQL server, the full
request flow was exercised against an in-memory stand-in for
`repositories.user_repository`. That covers routes, services, CSRF, sessions,
headers and template rendering — everything except the DDL itself.

**19 checks, all passing.**

| # | Check | Result |
|---|---|---|
| 1 | Stage 1 `/` still returns JSON 200 | Pass |
| 2 | `GET /register` renders all four fields + CSRF token | Pass |
| 3 | POST without a CSRF token is rejected (400) | Pass |
| 4 | Mismatched passwords rejected server-side | Pass |
| 5 | Registration succeeds and redirects to `/login` | Pass |
| 6 | Password stored hashed, not plaintext (`scrypt:32768:8:1$…`) | Pass |
| 7 | `GET /profile` while logged out redirects to `/login` | Pass |
| 8 | Wrong password shows "Invalid email or password." (401) | Pass |
| 9 | Unknown email shows the *same* message (401) | Pass |
| 10 | Wrong-password and unknown-email responses are indistinguishable | Pass¹ |
| 11 | Correct credentials redirect to `/profile` | Pass |
| 12 | Session cookie is `HttpOnly` | Pass |
| 13 | Session cookie is `SameSite=Lax` | Pass |
| 14 | Profile shows the user's name and email | Pass |
| 15 | Protected pages send `Cache-Control: no-store` | Pass |
| 16 | Header shows the user menu with Log Out when logged in | Pass |
| 17 | `GET /logout` is not allowed (405) | Pass |
| 18 | `POST /logout` redirects to `/login` | Pass |
| 19 | After logout, `/profile` redirects to `/login` | Pass |

¹ This check initially reported a failure. Investigation showed the two
responses differed only by (a) the per-session CSRF token and (b) the email
echoed back into the form field — the assertion was comparing raw bytes and was
too strict. After normalising those two values the bodies are identical, with an
empty diff. The finding was a faulty test, not an enumeration leak; the
assertion was the thing at fault, and the behaviour is correct.

All Python modules compile cleanly (`compileall` exit 0) and all six templates
parse under Jinja.

### Definition of Done

- [x] Can register a new account and see it hashed (not plaintext) in `users`
- [x] Can log in with correct credentials and get redirected to a landing page
- [x] Wrong password shows a generic error, not "user not found" vs "wrong password"
- [x] Visiting a `login_required` page while logged out redirects to `/login`
- [x] Logging out and pressing Back does not show protected content
- [x] Session cookie is HttpOnly and SameSite=Lax

---

## 8. Interpretations and open items

**"Landing/dashboard page."** The DoD says a successful login redirects to a
landing/dashboard page, but Stage 2 defines no dashboard route. Login therefore
redirects to `/profile`, the only logged-in page this stage specifies. Inventing
a dashboard would have pulled work forward from a later stage.

**`GET /` stays JSON.** Stage 1 defined `/` as an unauthenticated JSON status
endpoint, and Stage 2 did not ask for that to change, so it was left alone. The
header brand link points at `/profile` when logged in and `/login` otherwise, so
nobody is routed to the JSON page through the UI.

**The DDL has not been run against a live MySQL.** `scripts/create_tables.py`
was syntax-checked but not executed against a real server, because none was
available in the sandbox. The first genuine run is `python -m scripts.create_tables`
on the development machine.

---

## 9. Notes for Stage 3

- The session currently holds `user_id` and `full_name`. Stage 3 adds
  `organization_id` and `role`; `utils/auth.py::start_session()` is the single
  place that writes session state, so that is where they go.
- `login_required` is in `utils/auth.py` and is the natural place for a
  role-aware variant to sit alongside.
- CSRF is already global — new POST routes are protected automatically and need
  only the hidden field in their form.
- The `users` table has no `organization_id` yet. Stage 3 introduces
  multi-tenancy, at which point every tenant-scoped query must filter by it.
- The color and typography tokens in `static/style.css` are the shared
  vocabulary; later stages should add components using those variables rather
  than literal hex values, so dark mode keeps working.
