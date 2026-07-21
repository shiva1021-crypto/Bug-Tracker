# Stage 3 - Multi-Tenancy & Roles · Completion Report

**Project:** Bug Tracker (Jira-style bug tracking & agile project management)
**Stage:** 3 of 10 - Multi-Tenancy & Roles
**Spec:** `project-spec/03-multi-tenancy-roles.md`
**Builds on:** Stage 1 (Foundation & Setup), Stage 2 (Authentication)
**Status:** Complete and verified (routes/services/repositories/templates); DDL not yet run against a live MySQL server - see §6.
**Date:** 21 July 2026

---

## 1. Goal of this stage

Turn the single-organization, roleless login system from Stage 2 into a
multi-tenant system: every user belongs to exactly one organization, four
roles exist, and an admin panel lets an organization manage its own members
and registration requests without ever seeing another organization's data.

Deliberately **not** built (each belongs to a later stage or was never asked for):

- No default project auto-created on new-org registration. The spec's DoD
  mentions this, but Stage 3's own "Features to build" and data-model
  sections define no `projects` table or route - that arrives in Stage 4.
  Building it now would mean inventing a Stage 4 schema early, which the
  process rules explicitly forbid. See §8 for the full reasoning.
- No enforcement of the role permission matrix (create/edit/assign issues,
  manage sprints, etc.) - there are no issues, sprints, or boards yet to
  gate. The matrix is documented in the spec as something *future* stages
  must enforce; Stage 3 only establishes `role` as a fact about each user.
- No project/issue/board/report UI. The sidebar is introduced as a shell
  (per the spec) but only carries the one link Stage 3 actually needs
  ("Users", admin-only) - later stages add Board, Backlog, Reports, etc. to
  the same shell without changing its structure.
- No self-service "forgot my org" or "which orgs am I in" flows - a user
  belongs to exactly one organization, permanently, as specified.

Stages 1 and 2 were left intact except where Stage 3 explicitly requires a
change (the `users` table gains columns; the session gains fields; the
register route gains a field). Nothing already working was rewritten.

---

## 2. What was built

### 2.1 New files

| File | Layer | Purpose |
|---|---|---|
| `repositories/organization_repository.py` | repositories | SQL for `organizations`: create, get by name, get by id. |
| `repositories/registration_request_repository.py` | repositories | SQL for `registration_requests`, every query organization-scoped. |
| `services/admin_service.py` | services | Fresh admin verification, member list, role changes, approve/reject. |
| `routes/admin_routes.py` | routes | `/admin/users` and the role-change / approve / reject POST routes. |
| `templates/auth/pending.html` | frontend | "Request submitted, awaiting approval" notice. |
| `templates/admin/users.html` | frontend | Member table + pending-requests table. |

### 2.2 Modified files

| File | Change |
|---|---|
| `scripts/create_tables.py` | Adds `organizations` and `registration_requests` DDL; migrates the existing `users` table to add `organization_id` + `role` safely (see §5.1). |
| `repositories/user_repository.py` | `create()`/`get_by_email()`/`get_by_id()` now carry `organization_id` + `role`; added `get_by_id_and_org()`, `list_by_organization()`, `update_role()`. |
| `services/auth_service.py` | `validate_registration()` takes `organization_name`; `register()` now branches into "create org, become admin" vs. "file a pending request"; `authenticate()` returns `organization_id`/`role`. |
| `routes/auth_routes.py` | `/register` reads the new field and branches on the service's result; added `GET /register/pending`. |
| `utils/auth.py` | `start_session()`/`current_user()` carry `organization_id` and `role`. |
| `app.py` | Registers `admin_bp`. |
| `templates/base.html` | Adds the collapsible sidebar shell and its toggle button. |
| `templates/auth/register.html` | Adds the Organization Name field + helper text. |
| `static/style.css` | Sidebar/shell layout, admin data-table styles, `.btn-success`/`.btn-danger`/`.btn-sm`, pending-page styles. |
| `static/script.js` | Sidebar collapse/expand toggle. |

### 2.3 Layering

No new patterns - Stage 3 slots into the existing chain:

```
routes/admin_routes.py        reads the form, redirects or renders
   ↓
services/admin_service.py     fresh role check, org-scoped business rules
   ↓
repositories/*_repository.py  the only modules that write SQL
   ↓
utils/db.py                   pooled connection from Stage 1 (unchanged)
```

`utils/auth.py` stays database-free, exactly as in Stage 2 - it only reads
and writes the Flask session. The one new requirement this stage adds
("re-check the role from the database on sensitive actions") is *not*
implemented there; it lives in `admin_service.verify_admin()`, which every
admin route calls before doing anything. See §5.2 for why.

---

## 3. Data model

**Table: `organizations`** - new.

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK AUTO_INCREMENT | |
| `name` | VARCHAR(150) | UNIQUE, NOT NULL |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP |

**Table: `users`** - altered.

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK AUTO_INCREMENT | unchanged |
| `full_name` | VARCHAR(150) | unchanged |
| `email` | VARCHAR(150) | unchanged - still globally UNIQUE |
| `password_hash` | VARCHAR(255) | unchanged |
| `organization_id` | INT | **new.** NOT NULL, FK → `organizations(id)`, ON DELETE CASCADE |
| `role` | ENUM('admin','project_manager','developer','tester') | **new.** NOT NULL, DEFAULT `'tester'` |
| `created_at` | DATETIME | unchanged |

**Table: `registration_requests`** - new.

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK AUTO_INCREMENT | |
| `organization_id` | INT | FK → `organizations(id)`, ON DELETE CASCADE |
| `full_name` | VARCHAR(150) | |
| `email` | VARCHAR(150) | *not* unique here - see §5.3 |
| `password_hash` | VARCHAR(255) | |
| `requested_role` | ENUM(...) | same 4 values, DEFAULT `'tester'` |
| `requester_ip` | VARCHAR(45) | from `request.remote_addr` |
| `status` | ENUM('pending','approved','rejected') | DEFAULT `'pending'` |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP |

All three use `ENGINE=InnoDB`, `utf8mb4` / `utf8mb4_unicode_ci`, matching
the rest of the schema.

---

## 4. Routes delivered

| Method | Path | Auth | Behaviour |
|---|---|---|---|
| GET | `/register` | none | Now also renders the Organization Name field. |
| POST | `/register` | none | New org name → creates org + admin account, logs in, redirects to `/profile`. Existing org name → creates a `registration_requests` row, redirects to `/register/pending`. Validation failures re-render at 400, as before. |
| GET | `/register/pending` | none | Static "request submitted, awaiting approval" notice. No sidebar (no session exists to show one). |
| GET/POST | `/login` | none | Unchanged behaviour; session now additionally carries `organization_id` and `role`. |
| POST | `/logout` | none | Unchanged. |
| GET | `/profile` | required | Unchanged. |
| GET | `/admin/users` | **Admin only** | Member table + pending-requests table, both scoped to the caller's organization. |
| POST | `/admin/users/<id>/role` | **Admin only** | Changes a member's role. `<id>` is verified to belong to the caller's org before anything is written. |
| POST | `/admin/requests/<id>/approve` | **Admin only** | Creates the real `users` row from the request, marks it `approved`. |
| POST | `/admin/requests/<id>/reject` | **Admin only** | Marks the request `rejected`. No account created. |

**Session contents after login:** `user_id`, `full_name`, `organization_id`, `role`.

---

## 5. Key design decisions

### 5.1 Migrating `users` without breaking Stage 2 accounts

Stage 2's `users` table has no `organization_id`. The spec's DDL wants that
column `NOT NULL`, but a straight `ALTER TABLE ... ADD COLUMN organization_id
INT NOT NULL` would fail outright on any database that already has rows -
and this one might, since the user was told to test Stage 2 by hand.

`scripts/create_tables.py` now:

1. Checks `information_schema.COLUMNS` before adding `organization_id` or
   `role`, so re-running the script is always a no-op on a database that
   already has them.
2. If `organization_id` needs to be added, it is added **nullable** first.
3. Any row left with `organization_id IS NULL` (i.e. every pre-Stage-3
   account) is backfilled into a single new organization named
   **"Legacy Organization"**, as **admin** - so nobody who already made an
   account loses access to it.
4. Only then is the column tightened to `NOT NULL`, and the FK constraint is
   added (also checked against `information_schema.TABLE_CONSTRAINTS` first).

On a brand-new database this whole backfill path is skipped - there are no
orphan rows - and the net effect is identical to running the spec's DDL
directly. The extra logic exists purely so the script stays safe to run
against whatever state the user's real `bug_tracker_db` is actually in.

### 5.2 The fresh-role-check lives in the service layer, not `utils/auth.py`

The spec requires: *"Re-check the role from the database on sensitive
actions rather than trusting a stale session value indefinitely."*

`utils/auth.py::login_required` is a pure session check with no database
access - that was true in Stage 2 and stays true now, because Stage 1's
layering rule is routes → services → repositories → utils, and utils sits
below repositories. Having a "cross-cutting" auth helper reach *up* into
`repositories.user_repository` would invert that dependency and make the
layering harder to reason about for every stage after this one.

Instead, `services/admin_service.py::verify_admin(user_id)` does the fresh
read, and every route in `routes/admin_routes.py` calls it first, before
touching anything else. The session's cached `role` (in `current_user()`)
is used only for cosmetic decisions - whether to render the "Users" sidebar
link - never for gating an actual action. This was verified directly (see
check #29–31 in §7): promoting a logged-in user to admin from a second
session takes effect on that user's *very next* request, with no re-login,
and the reverse (a demoted admin) would be caught the same way.

### 5.3 `registration_requests.email` is not unique, `users.email` still is

A person could type the same email into two different organizations'
registration forms before either is approved (or retry after a typo).
Making `registration_requests.email` UNIQUE would block that unnecessarily.
What actually matters - no two *accounts* sharing an email - is still
guaranteed by `users.email UNIQUE`, unchanged since Stage 2.

To avoid confusing duplicate pending requests, `validate_registration()`
also checks `registration_request_repository.pending_email_exists()` and
rejects a second pending request for an email that already has one. And
`admin_service.approve_request()` re-checks `email_exists()` immediately
before creating the account, in case the same email was approved elsewhere
(or registered directly as a new org) in the meantime - if so, the request
is auto-rejected instead of crashing on the UNIQUE constraint.

### 5.4 Organization-name matching is case-insensitive for free

`organizations.name` uses the same `utf8mb4_unicode_ci` collation as
`users.email` did in Stage 2 - which compares (and enforces UNIQUE)
case-insensitively. "Acme Corp" and "acme corp" resolve to the same
organization without any extra normalization code, the same way
`Ada@Example.com` and `ada@example.com` already resolved to the same
account. This was verified directly (check #9): registering into "acme
corp" after "Acme Corp" already exists creates a second *pending request*,
not a second organization.

### 5.5 A pending registrant does not get a session - interpretation call

The spec's DoD says *"A pending user cannot access any page except a
'pending approval' notice."* Read literally, this could imply a pending
person can log in and be shown a special page. But the spec's own data
model gives pending signups **no `users` row at all** - only a
`registration_requests` row, with no `status` column on `users` to make
such a login meaningful. Adding one would be inventing schema the spec
didn't ask for.

The reading implemented: after submitting a request to join an existing
org, the person is redirected straight to `/register/pending` (no session
started) - that *is* "the only page they can access," because there is
nothing else to log into yet. If they try `/login` before approval,
`authenticate()` returns `None` exactly as it would for any unknown email,
and they see the same generic "Invalid email or password." This was a
deliberate choice, not an oversight: Stage 2 established that login
failures must never reveal whether an account exists, and a distinct
"your request is still pending" message on the login form would be exactly
that kind of leak. Flagging this explicitly in case the intended UX was
different - happy to add a distinguishable pending-login state if wanted,
but it would need a schema change beyond what Stage 3 specifies.

### 5.6 Requested role on a join request defaults to `tester`

The register form (per the spec's frontend section) has no role picker -
only Organization Name, Full Name, Email, Password. So a join request needs
some default `requested_role`. `tester` was chosen because it is already
the lowest-privilege role and the column's own default in the `users`
table; an admin can assign anything else at approval time via the role
dropdown on the same page. No self-service role selection was added, since
the spec doesn't ask for one and it would let anyone request Admin for
themselves.

### 5.7 No self-role-lockout guard - and why that's correct, not missing

An admin can change their own role, including away from `admin`, with no
special-cased warning. This is intentional rather than an oversight: because
every admin route re-verifies the role fresh from the database (§5.2), an
admin who demotes themselves is correctly locked out of `/admin/users` on
their very next request - which is the exact behavior the spec's freshness
requirement describes. Adding a guard against it would be extra scope the
spec doesn't ask for, on top of behavior the fresh-check already handles
correctly by design.

### 5.8 Sidebar is a real Jinja block, not two copies of one

The sidebar had to be introduced without duplicating `{% block content %}`
across a logged-in/logged-out branch - Jinja resolves block names statically
across a whole template, so defining `content` (or `main_class`) twice, even
in an `{% if %}/{% else %}`, raises `TemplateAssertionError: block '...'
defined twice` at render time (this was caught during verification, see
§7). `base.html` now always renders one `<div class="app-shell">` containing
exactly one `<main>` with the blocks; the `<aside>` sidebar is the only part
that is conditional on `current_user`. Logged-out pages (login, register,
the pending notice) simply get no `<aside>`, which satisfies the spec's "no
sidebar" requirement for the pending page without a second template shell.

---

## 6. Setup procedure

```bash
python -m scripts.create_tables     # adds organizations, registration_requests;
                                     # migrates users (org_id + role, backfilled)
python run.py                       # → http://127.0.0.1:5000
```

`requirements.txt` is unchanged - no new packages were needed for this stage.

**Important:** if you already have accounts from testing Stage 2, running
`create_tables` will move them into a new organization called **"Legacy
Organization"** and make all of them Admins there (see §5.1). That is a
one-time, one-way migration path for continuity - check the "Users" page
after upgrading if you want to review who ended up where.

---

## 7. Verification results

The sandbox used for development has no MySQL server, so - as in Stage 2 -
the full request flow was exercised against an in-memory stand-in for
`repositories.organization_repository`, `repositories.user_repository`, and
`repositories.registration_request_repository`. That covers routes,
services, CSRF, sessions, role gating, and template rendering; it does not
touch the DDL itself (see the open item in §8).

**37 checks, all passing** (one initial failure in the harness itself was a
test-authoring mistake - promoting a user to `project_manager` and then
asserting they could reach an *Admin-only* page, which the permission
matrix correctly says they can't; the assertion was fixed, the code was
never wrong).

| # | Check | Result |
|---|---|---|
| 1 | `GET /register` renders the new Organization Name field | Pass |
| 2–3 | New-org registration redirects (not 400/error) straight to `/profile` | Pass |
| 4–5 | Session holds `role=admin` and the new `organization_id` after new-org registration | Pass |
| 6 | The new admin can immediately view `/profile` | Pass |
| 7 | Registering into an *existing* org shows the pending-approval page | Pass |
| 8 | No session/`user_id` is created for a pending registrant | Pass |
| 9 | Organization name matching is case-insensitive (no duplicate org created) | Pass |
| 10 | Two pending requests correctly queued for one org | Pass |
| 11 | A pending registrant cannot log in yet - generic "Invalid email or password" | Pass |
| 12 | The org's admin can log back in | Pass |
| 13 | Admin sees the "Users" sidebar link | Pass |
| 14–17 | `/admin/users` (200 for admin) lists members and pending requests, including requester IP | Pass |
| 18–21 | Approving a request creates the real account with the default `tester` role and flips status to `approved` | Pass |
| 22–23 | Rejecting a request creates no account and flips status to `rejected` | Pass |
| 24–25 | The newly-approved user can log in; session role matches what was approved | Pass |
| 26–28 | A non-admin (tester) sees no "Users" link and is redirected with a flash from `/admin/users` | Pass |
| 29–31 | **Fresh-role-check:** promoting a user to admin from a second session takes effect on their *very next request* in their *original* session - no re-login required, even though that session's cached role is stale | Pass |
| 32–33 | A second organization's admin panel lists only that organization's own members | Pass |
| 34–35 | An admin cannot change a user's role in another organization (id rejected, target role unaffected) | Pass |
| 36 | An admin cannot approve/reject another organization's registration request | Pass |
| 37 | Admin POST routes reject a request with a missing/invalid CSRF token (400), same as every other POST route since Stage 2 | Pass |

All Python modules compile cleanly (`py_compile`, exit 0) and all 8
templates parse under Jinja with no syntax errors (this is also how the
`block 'main_class' defined twice` bug from an earlier draft of
`base.html` was caught and fixed before this report - see §5.8).

### Definition of Done

- [x] Registering a brand-new org name makes you Admin immediately
- [ ] ...with a default project auto-created - **not built**, see §8
- [x] Registering an existing org name creates a pending request, not an active account
- [x] A pending user cannot access any page except a "pending approval" notice (see §5.5 for the exact interpretation)
- [x] An Admin from Org A cannot see or approve requests from Org B
- [x] Every list/detail query added from this stage onward includes `WHERE organization_id = %s`
- [x] Changing a user's role takes effect on their next request, not just at their next login

---

## 8. Interpretations and open items

**The "default project auto-created" DoD line was not built.** Stage 3's
own "Features to build" list and data-model section say nothing about
projects - no table, no route, no field. That concept (and its schema)
belongs entirely to Stage 4 ("Projects & Issue Keys"), per the stage
breakdown in `00-README.md`. Building it now would mean guessing at a
`projects` table shape before Stage 4 defines one, which directly
contradicts the process rule "do not add anything from a later stage -
even if it seems obviously needed soon." This is flagged rather than
quietly built, per the same rule.

**Pending-registrant login experience (§5.5).** The chosen behavior - no
session, straight to `/register/pending`, and a generic login failure if
they try early - is the minimal reading consistent with the spec's own
table design (no `status` column on `users`) and with Stage 2's
anti-enumeration guarantee. If a distinguishable "your request is pending"
login state is actually wanted, it needs a small schema addition beyond
what Stage 3 specifies, and should be a deliberate decision rather than
something inferred here.

**Requested-role default (§5.6).** New join requests default to `tester`
since the register form has no role picker in the spec. An admin can
correct it in one click from `/admin/users`.

**The DDL has not been run against a live MySQL.** Exactly as in Stages 1–2,
`scripts/create_tables.py` was syntax-checked (`py_compile`) and its logic
was reasoned through carefully (see §5.1), but the sandbox has no MySQL
server to actually execute it against. In particular, the "Legacy
Organization" backfill path for pre-existing Stage-2 rows has not been
exercised against a real table with real rows - please run
`python -m scripts.create_tables` on the development machine and check the
printed output, then look at `/admin/users` to confirm any old accounts
landed where expected.

**Self-demotion is unguarded, by design (§5.7).** Worth restating here
since it is easy to mistake for a gap: it isn't one. The fresh-role-check
already produces the correct outcome if an admin removes their own admin
role.

---

## 9. Notes for Stage 4

- `organization_id` is now on `users`. Every new table Stage 4 introduces
  (starting with `projects`) needs its own `organization_id` and must
  filter by it, per the README's multi-tenancy rule - `user_repository.py`
  and the two new repositories in this stage are the reference pattern for
  what that looks like (`get_by_id_and_org`, `list_by_organization`, etc.).
- The sidebar shell now exists in `base.html` with exactly one link
  ("Users", admin-only). Stage 4+ should add links into the same
  `<nav class="sidebar-nav">` block rather than introducing a second nav
  structure - the collapse/expand toggle in `static/script.js` already
  applies to the whole `<aside>`.
- `current_user()` now carries `organization_id` and `role` from the
  session, but that value is a login-time snapshot. Anything that gates a
  real action (not just a cosmetic sidebar/nav decision) must re-verify
  against the database first, the way `admin_service.verify_admin()` does
  - this matters even more once Stage 5+ adds per-issue permission checks
  ("own reports only" for Developers/Testers).
- The "default project auto-created on new-org registration" DoD line from
  this stage's spec was deferred to Stage 4 (see §8) - Stage 4 should
  either implement it as part of its own "new project" flow, or explicitly
  decide it doesn't apply to registration and say so.
- `services/admin_service.py::ROLES` / `ROLE_LABELS` are the canonical list
  of the four roles and their display names; reuse them rather than
  re-declaring the role list elsewhere (e.g. an issue-assignment dropdown
  filtered to non-Tester roles in a later stage).
