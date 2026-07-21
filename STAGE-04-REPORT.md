# Stage 4 — Projects & Issue Keys · Completion Report

**Project:** Bug Tracker (Jira-style bug tracking & agile project management)
**Stage:** 4 of 10 — Projects & Issue Keys
**Spec:** `project-spec/04-projects-issue-keys.md`
**Builds on:** Stage 1 (Foundation), Stage 2 (Authentication), Stage 3 (Multi-Tenancy & Roles)
**Status:** Complete and verified (routes/services/repositories/templates); DDL not yet run against a live MySQL server — see §6.
**Date:** 21 July 2026

---

## 1. Goal of this stage

Let an organization split its work into projects, each with a short
uppercase key, so issues can later be identified like `WEB-1`. Admins and
Project Managers can create projects; anyone in the org can see the list;
a brand-new organization gets a "General" project automatically so there's
always somewhere to work.

Deliberately **not** built (belongs to a later stage, or has no caller yet):

- No issues, no issue creation, no `WEB-1`-style keys actually assigned —
  that's Stage 5. This stage only builds the counter (`next_issue_number`)
  that Stage 5 will consume.
- No real project board — clicking a project card goes to a placeholder
  detail page, exactly as the spec's frontend section asks for ("for now
  it can just show a placeholder detail page"). The real board is Stage 7.
- No project editing or deletion — the spec's feature list only asks for
  create + list.
- No enforcement of the full Stage 3 permission matrix beyond "who can
  create a project" — there's still nothing to assign, edit, or sprint-plan.

Stages 1–3 were left intact except for the one line Stage 4's own DoD
requires: `auth_service.register()`'s new-organization path now also
creates the default project (see §5.1 — this was flagged as an open item
in `STAGE-03-REPORT.md` §8/§9, and is resolved here rather than deferred
again).

---

## 2. What was built

### 2.1 New files

| File | Layer | Purpose |
|---|---|---|
| `repositories/project_repository.py` | repositories | SQL for `projects`: list/get (org-scoped), key-exists check, create, and the concurrency-safe issue-number allocator (unused until Stage 5 — see §5.4). |
| `services/project_service.py` | services | Fresh Admin/PM verification, validation (name, key format, per-org key uniqueness), project creation, default-project creation. |
| `routes/project_routes.py` | routes | `GET /projects`, `POST /projects/create`, `GET /projects/<id>` (placeholder detail). |
| `templates/projects/list.html` | frontend | Project card grid + inline "+ New Project" form (Admin/PM only). |
| `templates/projects/detail.html` | frontend | Placeholder project page. |

### 2.2 Modified files

| File | Change |
|---|---|
| `scripts/create_tables.py` | Adds the `projects` table DDL, including the `(organization_id, project_key)` unique constraint. |
| `services/auth_service.py` | New-organization registration now also calls `project_service.create_default_project()`. |
| `app.py` | Registers `project_bp`. |
| `templates/base.html` | Adds a "Projects" sidebar link, visible to every role (unlike "Users", which stays Admin-only). |
| `static/style.css` | Project grid/card/badge styles, `.page-head`, `.btn-secondary`, inline-form toggle styles. |
| `static/script.js` | "+ New Project" show/hide toggle. |

### 2.3 Layering

No new patterns — Stage 4 slots into the same chain as Stage 3:

```
routes/project_routes.py      reads the form, redirects or renders
   ↓
services/project_service.py   fresh role check, validation, org-scoped rules
   ↓
repositories/project_repository.py   the only module that writes project SQL
   ↓
utils/db.py                   pooled connection from Stage 1 (unchanged)
```

Project creation is gated the same way admin actions are: `verify_project_creator()`
re-reads the role from the database on every request, exactly like
`admin_service.verify_admin()` — the session's cached role only decides
whether to show the "+ New Project" button, never whether the POST is
allowed. This was verified directly (see checks #20–22 in §7): a Developer
gets no button, and a direct POST to `/projects/create` is still rejected
server-side.

---

## 3. Data model

**Table: `projects`** — new.

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK AUTO_INCREMENT | |
| `organization_id` | INT | NOT NULL, FK → `organizations(id)`, ON DELETE CASCADE |
| `name` | VARCHAR(150) | NOT NULL |
| `project_key` | VARCHAR(10) | NOT NULL, always stored uppercase (enforced in the service layer — see §5.2) |
| `description` | TEXT | nullable |
| `next_issue_number` | INT | NOT NULL, DEFAULT 1 |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP |

`UNIQUE (organization_id, project_key)` — two projects in the same org
can't share a key; two different orgs can each have their own `WEB`. Same
`ENGINE=InnoDB`, `utf8mb4`/`utf8mb4_unicode_ci` as every other table.

---

## 4. Routes delivered

| Method | Path | Auth | Behaviour |
|---|---|---|---|
| GET | `/projects` | required | Lists every project in the caller's organization. "+ New Project" button shown only if the session's cached role is Admin or PM. |
| POST | `/projects/create` | **Admin/PM only** | Validates name + key, creates the project. Freshly re-checks the caller's role before doing anything (see §2.3). Duplicate key in the same org → 400 with a clear flashed error, form re-opened with values retained. |
| GET | `/projects/<id>` | required | Placeholder detail page. An id belonging to another organization (or that doesn't exist) redirects to `/projects` with a "Project not found" flash — behaves identically to a nonexistent id, so no cross-org information leaks through numeric guessing. |

No new session fields — this stage reads `organization_id`/`role` from the
session established in Stage 3, and re-verifies role via the database for
the one action that needs it (creating a project).

---

## 5. Key design decisions

### 5.1 The "General" project is created inside `auth_service.register()`, not as a separate step

Stage 3's own report flagged this exact gap: its Definition of Done
mentioned a default project, but Stage 3 had no `projects` table to create
one in, so it was deliberately deferred. Stage 4 resolves it the way that
report suggested — the new-organization branch of `auth_service.register()`
now calls `project_service.create_default_project(organization_id)`
immediately after the organization and its admin user are created, in the
same request. This was verified directly (checks #1–5, #14 in §7): a
brand-new organization has exactly one project, named `General`, keyed
`GEN`, with `next_issue_number` at 1, before the registrant's very first
page load.

### 5.2 The key is normalized to uppercase by the server, not required from the user

The spec's column note says `project_key` is "uppercase," and the create
form's helper text says the same, but nothing requires the *user* to type
it that way. `project_service.create_project()` uppercases whatever was
submitted before it ever reaches the repository layer — so typing `web`
and `WEB` produce the identical, single project. This mirrors how email
was lowercased server-side in Stage 2 and organization names matched
case-insensitively in Stage 3: normalization is the server's job, not
something client input is trusted to have already done. Verified directly
(checks #9–10): submitting `web` stores `WEB`.

### 5.3 Duplicate-key validation is organization-scoped, exactly like the spec's DoD

`project_service.validate_project()` checks `project_repository.key_exists(organization_id, project_key)`
— scoped to the *caller's* organization, using the id from the freshly
verified creator, never a client-supplied value. Two different
organizations creating a `WEB` project is not a conflict (checks #15–16);
the same organization trying to create a second `WEB` is rejected with a
clear error naming the key (checks #11–12). A malformed key (wrong length,
non-letters) is rejected before the database is ever queried (check #13).

### 5.4 The concurrency-safe issue-number allocator is built now, called by nobody yet

The spec's own Backend section, inside Stage 4's text, states a rule to
"implement carefully": issue-number allocation must read and increment
`next_issue_number` inside the same transaction as the issue insert, using
`SELECT ... FOR UPDATE` to lock the project's row, so two concurrent issue
creates can never collide. Nothing in Stage 4 creates issues — that starts
in Stage 5 — but the sentence itself is part of *this* stage's spec, not
an inference from a later one, so `project_repository.allocate_next_issue_number()`
was written now, sitting next to the table it locks, with a docstring
explaining it takes the caller's existing connection (so it can share a
transaction with an issue insert) rather than opening its own the way
every other function in this module does. It is intentionally unused —
there is nothing yet to call it — and is flagged here rather than wired to
a route so Stage 5 can call it, decide how to use its return value, and
own the transaction boundary around the issue insert itself.

### 5.5 The "Projects" sidebar link is visible to everyone; "Users" stays Admin-only

Viewing `/projects` has no role restriction in the spec — only *creating*
a project does. So the sidebar link added in Stage 3's shell now carries
two entries: "Projects" (all roles) and "Users" (Admin only, unchanged).
This was verified directly for a Developer role (check #20): no "+ New
Project" button, but the page and its project list still render.

### 5.6 A cross-organization project id behaves exactly like a nonexistent one

`GET /projects/<id>` calls `project_repository.get_by_id_and_org()`, which
returns `None` both when the id doesn't exist at all and when it belongs
to a different organization. The route can't tell those two cases apart —
by design — so both produce the identical "Project not found" redirect.
Verified directly (check #19): Beta Inc's admin, given Acme Corp's real
numeric project id, gets the same not-found flash a made-up id would
produce, not Acme's project.

### 5.7 No project editing/deletion, and no modal

The spec's feature list only asks for creating and listing projects, so
neither an edit form nor a delete action was built. The "+ New Project"
control is a simple inline `<details>`-style toggle (show/hide via
`static/script.js`, no new framework) rather than a modal dialog — the
spec explicitly offered "a small modal or inline form" as equivalent
options, and an inline form keeps the same plain-HTML-forms pattern every
other page in this codebase already uses, with no new UI machinery (focus
trapping, backdrop, escape-to-close) that a modal would need.

---

## 6. Setup procedure

```bash
python -m scripts.create_tables     # adds the projects table
python run.py                       # → http://127.0.0.1:5000
```

`requirements.txt` is unchanged — no new packages were needed for this stage.

---

## 7. Verification results

As in Stages 2–3, the sandbox used for development has no MySQL server, so
the full request flow was exercised against in-memory stand-ins for
`repositories.organization_repository`, `repositories.user_repository`,
`repositories.registration_request_repository`, and (new this stage)
`repositories.project_repository`. This covers routes, services, role
gating, org isolation, and template rendering; it does not touch the DDL
itself (see the open item in §8).

**22 new checks for this stage, all passing.** The full Stage 3 suite (37
checks) was also re-run against the updated codebase to confirm nothing
regressed — **all 37 still pass**, including registration, login, the
admin panel, and the fresh-role-check behavior.

| # | Check | Result |
|---|---|---|
| 1 | New-org registration still redirects to `/profile` (unchanged from Stage 3) | Pass |
| 2–5 | A brand-new organization has exactly one project, named `General`, keyed `GEN`, with `next_issue_number = 1`, immediately after registration | Pass |
| 6–8 | `GET /projects` is 200 for a logged-in user, lists `General`/`GEN`, and an Admin sees the "+ New Project" button | Pass |
| 9–10 | Creating a project with a lowercase key (`web`) succeeds and is stored as uppercase `WEB` | Pass |
| 11–12 | A duplicate key in the same organization is rejected with a clear error; no second row is created | Pass |
| 13 | A malformed key (wrong length / non-letters) is rejected before touching the database | Pass |
| 14 | A second organization (Beta Inc) also gets its own `General`/`GEN` project on registration | Pass |
| 15–16 | Two different organizations can each have a project keyed `WEB` with no conflict — genuinely distinct rows | Pass |
| 17–18 | Beta Inc's `/projects` shows only its own projects, not Acme's | Pass |
| 19 | Beta's admin, given Acme's real project id, gets "Project not found" — not Acme's project | Pass |
| 20 | A Developer sees no "+ New Project" button | Pass |
| 21–22 | A Developer's direct POST to `/projects/create` is rejected server-side (fresh role check), and creates nothing | Pass |

All Python modules compile cleanly (`py_compile`, exit 0) and all 10
templates (2 new this stage) parse under Jinja with no syntax errors.

### Definition of Done

- [x] Creating a project with a duplicate key (within the same org) is rejected with a clear error
- [x] Two different organizations can each have a project with the key `WEB` without conflict
- [x] A Developer/Tester cannot see a "New Project" button (role enforced both in the UI and on the server)
- [x] A brand-new organization has exactly one project ("General") immediately after registration

---

## 8. Interpretations and open items

**The issue-number allocator has no caller yet (§5.4).** It was written
because the spec's own Stage 4 text asks for it, but it cannot be
meaningfully tested end-to-end until Stage 5 actually inserts an issue
inside the same transaction. Flagging this rather than treating it as
"done" — the locking behavior itself (does `FOR UPDATE` really serialize
two concurrent callers) has only been read through carefully, not
exercised under real concurrency, since there is no real issue insert to
pair it with yet.

**The DDL has not been run against a live MySQL.** Exactly as in Stages
1–3, `scripts/create_tables.py` was syntax-checked (`py_compile`) but the
sandbox has no MySQL server to execute it against. In particular, the
`UNIQUE (organization_id, project_key)` constraint and the FK to
`organizations` have not been confirmed against a real server — please run
`python -m scripts.create_tables` and check its output.

**Project key length is capped at the form's `maxlength="6"` plus a
2–6-letter server pattern**, matching the spec's example (`WEB`) and its
column definition (`VARCHAR(10)`, which leaves headroom the spec doesn't
otherwise explain — the extra space was left unused rather than guessed at).

**No numbers or hyphens in a project key.** The spec's example ("2–6
uppercase letters, e.g. `WEB`") only shows letters, so `PROJECT_KEY_PATTERN`
requires `[A-Z]{2,6}` exactly. If a numeric key like `WEB2` is actually
wanted, that's a one-line pattern change, flagged here rather than assumed.

---

## 9. Notes for Stage 5

- `projects.next_issue_number` and `project_repository.allocate_next_issue_number()`
  are ready to use. The function takes an existing connection (not one it
  opens itself) precisely so Stage 5's issue-insert code can call it inside
  the same transaction and commit both together — see §5.4 for the full
  contract.
- `project_repository.get_by_id_and_org()` / `key_exists()` are the
  reference pattern for any Stage 5 query that needs a project by id
  scoped to an organization.
- The placeholder `templates/projects/detail.html` is where Stage 5's
  issue list (and eventually Stage 7's board) should render — replacing
  the placeholder paragraph, not the page's header/badge structure.
- `services/project_service.py::CAN_CREATE_PROJECT_ROLES` (`admin`,
  `project_manager`) is the reference for any Stage 5 check that needs the
  same "Admin or PM" gate (e.g. assigning issues, per the Stage 3
  permission matrix) — reuse the fresh-DB-check pattern rather than
  trusting the session role.
