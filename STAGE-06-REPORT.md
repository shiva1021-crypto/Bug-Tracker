# Stage 6 — Workflow & Status · Completion Report

**Project:** Bug Tracker (Jira-style bug tracking & agile project management)
**Stage:** 6 of 10 — Workflow & Status
**Spec:** `project-spec/06-workflow-status.md`
**Builds on:** Stages 1-5 (Foundation, Authentication, Multi-Tenancy & Roles, Projects & Issue Keys, Core Issue CRUD & Hierarchy)
**Status:** Complete and verified (routes/services/repositories/templates); DDL not yet run against a live MySQL server — see §6.
**Date:** 21 July 2026

---

## 1. Goal of this stage

Give every issue a defined lifecycle (five ordered statuses), restrict who
can move it, and keep a full audit trail of every status change,
assignment change, and significant edit. Add threaded comments and a
per-user watch toggle.

Deliberately **not** built (belongs to a later stage):

- No Kanban board and no drag-and-drop status changes — Stage 7 owns the
  board; this stage's status control is a plain dropdown + submit button
  on the issue detail page.
- No actual email/notification delivery for watchers. The spec says so
  explicitly ("notifications themselves arrive in Stage 10") — this stage
  only stores the watch relationship correctly and exposes a watcher
  count.
- No sprint/backlog concept — that's Stage 8.
- No custom/configurable workflow definitions, even though keeping
  `bugs.status` a `VARCHAR` (not an `ENUM`) is explicitly *for* that future
  flexibility. This stage still only offers the fixed five-status list
  everywhere a status is chosen.

Stages 1-5 were left intact except for two small, spec-required additions
inside `services/issue_service.py` (a history entry on create and on edit
— see §5.1) and one column default change (see §5.2). No prior file was
rewritten; every other Stage 1-5 file is untouched.

---

## 2. What was built

### 2.1 New files

| File | Layer | Purpose |
|---|---|---|
| `repositories/comment_repository.py` | repositories | SQL for `comments`: insert, and org-scoped list ordered newest-first. |
| `repositories/bug_history_repository.py` | repositories | SQL for `bug_history`: insert, and org-scoped list ordered oldest-first, with joined names for the changer and both old/new assignees. |
| `repositories/watcher_repository.py` | repositories | SQL for `issue_watchers`: `is_watching`, `add`, `remove`, `count`. |
| `services/workflow_service.py` | services | `STATUSES`, the reusable `can_update_status` / `can_assign` permission checks, `change_status`, `assign_issue` (with the auto-transition rule), comment/history/watch orchestration. |

### 2.2 Modified files

| File | Change |
|---|---|
| `scripts/create_tables.py` | Adds `comments`, `bug_history`, `issue_watchers` DDL; changes `bugs.status`'s column default from `'To Do'` to `'Idea'`; adds an idempotent `_ensure_bugs_status_default()` migration step for databases that already ran Stage 5's version of this script. |
| `repositories/issue_repository.py` | Adds `update_status()` and `update_assignment()`. Also extends `get_detail_by_id_and_org()`'s join to include `assigned_to_name`, needed by the detail page's new assignment display. |
| `services/issue_service.py` | `DEFAULT_STATUS` changed from `"To Do"` to `"Idea"` (see §5.2). `create_issue()` now records a "created the issue" history row; `update_issue()` now takes a `changed_by_user_id` parameter and records an "edited the issue" history row. Everything else in this file — hierarchy validation, screenshot handling, `get_editor_permission` — is unchanged. |
| `routes/issue_routes.py` | Adds `POST /issues/<id>/status`, `POST /issues/<id>/assign`, `POST /issues/<id>/comment`, `POST /issues/<id>/watch`. `issue_detail()` now also computes and passes `statuses`, `can_change_status`, `can_assign`, `assignable_developers`, `comments`, `history`, `watching`, `watcher_count`. `edit_issue()`'s call to `issue_service.update_issue()` now passes the editor's id. |
| `templates/issues/detail.html` | Adds a colored status badge, a status-change form, a watch toggle, an assignment control in the sidebar, a comments section, and a collapsible history panel. |
| `static/style.css` | Per-status badge colors, watch-toggle button, status/assign form layout, comment list/form styles, collapsible history panel styles, a small `.text-muted` utility. |
| `static/script.js` | Adds `initHistoryToggle()`, following the exact show/hide pattern already used by `initNewProjectToggle()`. |

### 2.3 Layering

No new patterns — the same shape as every prior stage:

```
routes/issue_routes.py         reads the form, redirects with a flash
   ↓
services/workflow_service.py   permission checks (fresh DB read), auto-transition rule, orchestration
   ↓
repositories/*_repository.py   the only modules that write comment/history/watcher/status SQL
   ↓
utils/db.py                    pooled connection from Stage 1 (unchanged)
```

`can_update_status()` and `can_assign()` follow the exact fresh-DB-check
pattern established by `admin_service.verify_admin`,
`project_service.verify_project_creator`, and
`issue_service.get_editor_permission`: every call re-reads the role from
the database, never trusts the session's cached role. This is what makes
the Definition of Done's "a Tester cannot move status via the API even by
crafting the request" item hold — verified directly in §7.

---

## 3. Data model

**Altered `bugs`:** `status` stays `VARCHAR(50)` (already true since
Stage 5); its column default is changed from `'To Do'` to `'Idea'` so a
manual/direct insert matches the new canonical starting state (new issues
already get their status from `issue_service.DEFAULT_STATUS` at insert
time regardless — see §5.2).

**Table: `comments`** — new, matches the spec exactly.

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK AUTO_INCREMENT | |
| `bug_id` | INT | NOT NULL, FK → `bugs(id)` ON DELETE CASCADE |
| `user_id` | INT | NOT NULL, FK → `users(id)` |
| `comment` | TEXT | NOT NULL |
| `created_at` | DATETIME | DEFAULT `CURRENT_TIMESTAMP` |

**Table: `bug_history`** — new, matches the spec exactly.

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK AUTO_INCREMENT | |
| `bug_id` | INT | NOT NULL, FK → `bugs(id)` ON DELETE CASCADE |
| `changed_by` | INT | NOT NULL, FK → `users(id)` |
| `old_status` / `new_status` | VARCHAR(50) | nullable |
| `old_assigned_to` / `new_assigned_to` | INT | nullable, FK → `users(id)` ON DELETE SET NULL |
| `change_note` | VARCHAR(255) | free-text; used for the creation/edit entries — see §5.3 |
| `changed_at` | DATETIME | DEFAULT `CURRENT_TIMESTAMP` |

**Table: `issue_watchers`** — new, matches the spec exactly: composite
primary key `(bug_id, user_id)`, both columns `ON DELETE CASCADE`.

No `organization_id` column on any of the three new tables — the spec's
own table definitions don't include one, and each is always reached
through a join back to `bugs.organization_id` (see each repository's
`list_by_bug`/`is_watching` etc.), matching the pattern the spec's data
model actually describes rather than adding a redundant column.

---

## 4. Routes delivered

| Method | Path | Auth | Behaviour |
|---|---|---|---|
| POST | `/issues/<id>/status` | `can_update_status` (Admin/PM, or the assigned Developer) | Updates status, records a history row. Anyone else gets a flash + redirect, no change made. |
| POST | `/issues/<id>/assign` | `can_assign` (Admin/PM only) | Assigns/reassigns/unassigns; applies the auto-transition rule; records one or two history rows (see §5.4). |
| POST | `/issues/<id>/comment` | any logged-in user who can view the issue | Adds a comment. |
| POST | `/issues/<id>/watch` | any logged-in user | Toggles the caller's watch state on this issue. |

All four are org-scoped through `issue_service.get_issue()` (a genuine
404 if the issue doesn't exist or belongs to another org, matching
Stage 5's convention) before any permission or business logic runs.

---

## 5. Key design decisions

### 5.1 Creation and edits record history from inside `issue_service`, not `workflow_service`

The spec requires "every ... significant field edit" to appear in the
history table, and issue creation/editing already lives entirely in
Stage 5's `issue_service.py`. Rather than have `workflow_service` reach
into issue creation/editing (which would invert the dependency the two
modules should have), `create_issue()` and `update_issue()` each call
`bug_history_repository.record()` directly, with a plain `change_note`
("created the issue (WEB-3)" / "edited the issue") and no
status/assignment fields set. `workflow_service.py` owns every row where
old/new status or old/new assignment actually changed. The history
panel's template distinguishes the two shapes: a row with a `change_note`
renders as that sentence verbatim; a row with old/new status or
assignment renders as "changed status from X to Y" / "assigned to Z" /
"unassigned Z" — matching the spec's three example sentences.

### 5.2 `status`'s default changes from `"To Do"` (Stage 5) to `"Idea"` (Stage 6)

Stage 5's report flagged this default as an open interpretation call
between the spec's two suggested values. Stage 6's spec resolves it: the
five-status order is given explicitly as "Idea → To Do → In Progress →
Testing → Done," so `"Idea"` is now the correct starting state, and
keeping `"To Do"` would put every newly created issue one step ahead of
where the canonical order says it should start. `issue_service.DEFAULT_STATUS`
is updated, and `scripts/create_tables.py` gained `_ensure_bugs_status_default()`
— an idempotent `ALTER TABLE ... SET DEFAULT` — so a database that already
ran Stage 5's version of the script picks up the corrected default too,
not just brand-new databases.

### 5.3 Status transitions are not restricted to "next" in the list

The spec's frontend section says to show "a dropdown or a row of buttons
for the next valid status/statuses," which could be read as only allowing
forward, sequential movement (Idea → To Do, never Idea → Done directly).
That reading was rejected: the Definition of Done never tests for
rejecting a skip, the Backend section's only hard rule is the
assignment-driven To Do → In Progress auto-transition, and the spec
explicitly keeps `status` a `VARCHAR` rather than an `ENUM` "to keep it
flexible for future custom workflows" — a signal that this stage
shouldn't hard-code a strict linear pipeline that a later stage would
just have to relax. `workflow_service.STATUSES` is kept as an ordered
list purely so the dropdown renders in the canonical order; any status a
permitted user picks is accepted. Flagged here explicitly since it's a
judgment call, not a spec requirement either way.

### 5.4 Auto-transition and reassignment are recorded as two separate history rows, not one combined event

When assigning an unassigned "To Do" issue triggers the
To Do → In Progress auto-transition, `workflow_service.assign_issue()`
writes one row for the assignment change (`old_assigned_to`/`new_assigned_to`)
and, only if the status actually changed, a second row for the status
change (`old_status`/`new_status`). This was chosen over inventing a
third, combined history-sentence shape: the spec's own three example
sentences ("changed status from Y to Z", "assigned to Y", "edited the
issue") are each a single kind of change, so two rows that each render as
one of those existing shapes fit the given format better than a new
composite sentence would. Verified directly in §7 that both rows appear,
in the correct order (assignment first, then the status row it caused).

### 5.5 Assignable users are restricted to Developers in the caller's organization

The spec's frontend section says the reassignment dropdown lists
"developers in the project's organization" — read as: only accounts with
the `developer` role, in the same organization as the assigner (not the
wider set of every role, and not any organization). `workflow_service.assign_issue()`
enforces this server-side (rejecting a crafted request that tries to
assign a Tester, an Admin, or a user from a different organization),
independent of what the dropdown itself would ever let a real browser
submit. Verified directly in §7 with both a wrong-role and a wrong-org
assignee id.

### 5.6 Comments are a flat, newest-first list — "threaded" read as chronological threading, not nested replies

The spec calls comments "threaded, newest-first" but the data model gives
`comments` no `parent_comment_id` or similar column, and the frontend
section describes a single list, not nested reply boxes. This was read as
"threaded" meaning *the conversation is threaded through the issue over
time* (i.e., a chronological log of remarks), not nested/tree-structured
replies — a flat list ordered newest-first satisfies both the data model
as given and the frontend description. Flagged as an interpretation call
in case true threaded replies were actually intended; the schema would
need a self-referential column to support that, matching how `bugs.parent_id`
works.

---

## 6. Setup procedure

```bash
python -m scripts.create_tables     # adds comments, bug_history, issue_watchers; fixes status default
python run.py                       # -> http://127.0.0.1:5000
```

No new dependencies — everything in this stage uses the same Flask/
mysql-connector/Jinja stack already in `requirements.txt`.

---

## 7. Verification results

As in every prior stage, the sandbox has no MySQL server, so the full
request flow was exercised against in-memory stand-ins for every
repository touched this stage (`user_repository`, `project_repository`,
`issue_repository`, `comment_repository`, `bug_history_repository`,
`watcher_repository`), matching each real function's exact signature, and
driven through the real Flask app (`app.test_client()`) end-to-end:
routes → services → fake repositories → real Jinja templates.

**24 new checks for this stage, all passing.**

| # | Check | Result |
|---|---|---|
| 1-2 | A newly created issue defaults to status "Idea" and the badge renders it | Pass |
| 3-4 | A Tester's crafted `POST /issues/<id>/status` is rejected (status unchanged, permission-denied flash shown) | Pass |
| 5 | A Developer **not** assigned to the issue cannot change its status | Pass |
| 6 | The **assigned** Developer can change status | Pass |
| 7 | An Admin can change status as an override, regardless of assignment | Pass |
| 8-9 | Assigning an unassigned "To Do" issue auto-transitions it to "In Progress", and the assignment itself is persisted | Pass |
| 10 | Assigning an issue already in "Testing" leaves its status unchanged | Pass |
| 11 | A Developer (non-Admin/PM) cannot assign/reassign at all | Pass |
| 12-13 | The auto-transition produces two history rows, in the correct order (assignment, then status) | Pass |
| 14-16 | Two comments are recorded, returned newest-first, and both render on the detail page | Pass |
| 17-18 | Watching an issue is stored and the watcher count reflects it | Pass |
| 19 | The watch relationship survives a **different** user changing the issue's status | Pass |
| 20 | Un-watching removes the relationship | Pass |
| 21 | Assigning to a non-developer (a Tester) is rejected | Pass |
| 22 | Assigning to a developer from a **different** organization is rejected | Pass |
| 23-24 | `issue_service.update_issue()` (Stage 5's edit path) succeeds and records an "edited the issue" history row | Pass |

All modified/added Python modules compile cleanly (`py_compile`, exit 0),
and the issue detail template renders without error across every scenario
above (creator view, assigned-developer view, admin view, tester view —
each with a different combination of `can_change_status`/`can_assign`).

### Definition of Done

- [x] A Tester cannot move an issue's status via the API even if they craft the request directly
- [x] Assigning an unassigned "To Do" issue moves it to "In Progress" automatically; assigning an issue already "In Progress" or beyond does not change its status
- [x] Every status change and assignment appears in the history panel in the correct order
- [x] Watching an issue and then someone else changing its status is recorded (the watcher relationship persists correctly; actual email delivery is Stage 10, per the spec)

---

## 8. Interpretations and open items

**Full-flexibility status transitions (§5.3)** is the biggest judgment
call this stage: any permitted user can move a permitted issue to *any*
of the five statuses, not just the "next" one in sequence. This matches
the letter of the Definition of Done and the spec's own stated reason for
keeping `status` a `VARCHAR`, but flagged clearly in case a strict
linear-only pipeline was actually intended.

**Flat, newest-first comments (§5.6)** rather than nested/tree-structured
replies — the schema as specified has no parent-comment column, so
nested threading isn't representable without extending the data model
beyond what the spec's table definition gives. Flagged in case true
threaded replies are wanted; would need a `parent_comment_id`-style
column, mirroring `bugs.parent_id`.

**Two history rows for an auto-transitioning assignment (§5.4)** rather
than one combined sentence — flagged in case a single composite history
entry ("X assigned to Y, moving it to In Progress") was intended instead.

**The DDL has not been run against a live MySQL.** `scripts/create_tables.py`
was syntax-checked (`py_compile`) and reasoned through, but as in every
prior stage, the sandbox has no MySQL server to execute it against — in
particular, the four new/changed foreign keys on `bug_history` (two of
them pointing at `users` with `ON DELETE SET NULL`), the composite primary
key on `issue_watchers`, and the `ALTER TABLE bugs ALTER COLUMN status SET
DEFAULT 'Idea'` step have not been confirmed against a real server.
Please run `python -m scripts.create_tables` and check its output —
it should print a line for each of the three new tables plus a line
confirming the status default change, with no errors.

**No new stray files this stage.** Unlike Stage 5, nothing in this
stage's verification writes to the mounted project folder (no file
uploads are involved), so there is nothing to clean up.

---

## 9. Notes for Stage 7

- `bugs.status` is still a free `VARCHAR`, now defaulting to `"Idea"` and
  changeable to any of the five values via `workflow_service.STATUSES` —
  the board's columns should read directly from that same list so the two
  never drift apart.
- `workflow_service.can_update_status()` / `can_assign()` are the
  reference permission checks for anything the board needs to gate (e.g.
  drag-and-drop status changes should call `change_status()`, not
  reimplement the transition/auto-transition/history-recording logic).
- `issue_repository.update_status()` and `update_assignment()` are the
  only two functions that write to `bugs.status`/`bugs.assigned_to` after
  creation — the board should call through `workflow_service`, not these
  repository functions directly, so history keeps getting recorded.
- The detail page's status control, assignment control, and watch toggle
  are all plain forms (no JS required for the core action, only the
  history panel's show/hide is JS-driven) — the board can follow the same
  progressive-enhancement approach rather than requiring JS for a status
  change to work at all.
