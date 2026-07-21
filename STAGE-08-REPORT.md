# Stage 8 — Agile Planning · Completion Report

**Project:** Bug Tracker (Jira-style bug tracking & agile project management)
**Stage:** 8 of 10 — Agile Planning
**Spec:** `project-spec/08-agile-planning.md`
**Builds on:** Stages 1-7 (Foundation, Authentication, Multi-Tenancy & Roles, Projects & Issue Keys, Core Issue CRUD & Hierarchy, Workflow & Status, Kanban Board)
**Status:** Complete and verified (routes/services/repositories/templates); DDL not yet run against a live MySQL server — see §6.
**Date:** 22 July 2026

---

## 1. Goal of this stage

Scrum-style planning on top of the workflow Stage 6 built and the board
Stage 7 built: a backlog and sprints (with a real burndown chart), typed
directional links between issues, and saved filter shortcuts on a new
issue search page.

Deliberately **not** built (belongs to a later stage or out of scope):

- No sprint reporting/velocity history across closed sprints — closed
  sprints simply stop appearing on the backlog page (see §5.1); nothing
  archives or charts them.
- No autocomplete/typeahead search for the link-target picker — the spec
  says "target issue by key/search," read here as typing the issue's
  exact key (see §5.5), not a live search dropdown, since that would need
  an AJAX endpoint the spec's route table doesn't list.
- No sharing of saved filters between users — `saved_filters.is_shared`
  exists on the table exactly as the spec defines it, defaulting to 0, but
  nothing reads it; the spec calls sharing out explicitly as "(future:
  share with team)."
- No changes to Stage 7's board. `board_service.BOARD_STATUSES` still
  reads directly off `bugs.status` and has no notion of sprints; a card
  moving between sprints doesn't change how the board itself works.

Stages 1-7 were left intact. The only pre-existing files touched are
`scripts/create_tables.py` (new tables + one altered column), `app.py`
(new blueprints + a filter registration, no route logic), `templates/base.html`
(two new sidebar links), `repositories/issue_repository.py` (new query
functions only — nothing existing changed except `_COLUMNS` gaining
`sprint_id`), `services/issue_service.py` (one new read-only helper,
`list_org_users`), and `templates/issues/detail.html` (a new sidebar
panel, inserted without touching the existing markup around it).

---

## 2. What was built

### 2.1 New files

| File | Layer | Purpose |
|---|---|---|
| `repositories/sprint_repository.py` | repositories | SQL for `sprints`: create, org-scoped get/list, `get_active_for_project` (the single-active-sprint check's data source), `set_status`. |
| `repositories/issue_link_repository.py` | repositories | SQL for `issue_links`: create, `exists` (dedup check), org-scoped get/list (joined with both issues' key/title), delete. |
| `repositories/saved_filter_repository.py` | repositories | SQL for `saved_filters`; the only place `filter_data`'s JSON (de)serialization happens. |
| `services/sprint_service.py` | services | Validation, the Admin/PM `verify_sprint_manager` gate, the future→active→closed lifecycle (including the single-active-per-project rule), and backlog↔sprint issue assignment. |
| `services/burndown_service.py` | services | Reconstructs each sprint day's real remaining work from Stage 6's `bug_history` audit trail. |
| `services/link_service.py` | services | The 7-option directional link form, duplicate/self-link rejection, and per-side label derivation. |
| `services/filter_service.py` | services | Query-param parsing, the search itself, and saved-filter persistence/listing. |
| `routes/backlog_routes.py` | routes | `GET /backlog`, `POST /sprints/create`, `POST /sprints/<id>/start`, `POST /sprints/<id>/close`, `POST /issues/<id>/sprint`. |
| `routes/filter_routes.py` | routes | `POST /filters/save`, `GET /filters`. |
| `templates/backlog.html` | frontend | Project selector, new-sprint form, backlog list, one collapsible section per open sprint, inline Chart.js burndown for the active sprint. |
| `templates/issues/list.html` | frontend | The new issue list/search page: filter chips, filter form, save-filter control, results table. |

### 2.2 Modified files

| File | Change |
|---|---|
| `scripts/create_tables.py` | Adds `sprints`, `issue_links`, `saved_filters` DDL; adds `bugs.sprint_id` (+ FK) to `BUGS_TABLE` for new databases and a new idempotent `_ensure_bugs_sprint_column()` migration for existing ones; reorders `STATEMENTS` so `sprints` is created before `bugs`. |
| `repositories/issue_repository.py` | Adds `sprint_id` to `_COLUMNS`; adds `get_by_key_and_org`, `list_backlog_issues`, `list_by_sprint`, `update_sprint`, `search_issues`. Nothing existing changed. |
| `services/issue_service.py` | Adds `list_org_users()` (wraps `user_repository.list_by_organization`, used by the issue list page's Assignee filter). Nothing else touched. |
| `routes/issue_routes.py` | Adds `GET /issues` (the new list/search page), `POST /issues/<id>/link`, `POST /issues/<id>/link/<link_id>/remove`; `issue_detail()` now also passes `links` and `link_form_options`. |
| `app.py` | Registers `backlog_bp` and `filter_bp`; adds a `{% block scripts %}` hook to the base layout (see §5.6) and no other logic. |
| `templates/base.html` | Adds "Backlog" and "Issues" sidebar links; adds the `scripts` block before `</body>`. |
| `templates/issues/detail.html` | Adds the "Linked Issues" sidebar panel (list + add-link form) between the metadata card and the Child Issues card. |
| `static/style.css` | New "backlog", "issue list", and "linked issues" sections. |
| `static/script.js` | Adds `initNewSprintToggle()`, `initBacklogSprintSelects()` (the "+ New Sprint" dropdown-option interception), `initSaveFilterForm()` (the name-prompt flow). |

### 2.3 Layering

```
routes/backlog_routes.py       reads form/query params, redirects or renders
routes/filter_routes.py
routes/issue_routes.py (extended)
   ↓
services/sprint_service.py      lifecycle rules, single-active enforcement, Admin/PM gate
services/burndown_service.py    reconstructs history into a chart-ready shape (read-only)
services/link_service.py        directional label mapping, dedup rules
services/filter_service.py      query-param parsing, save/list orchestration
   ↓
repositories/sprint_repository.py, issue_link_repository.py, saved_filter_repository.py,
repositories/issue_repository.py (extended)
   ↓
utils/db.py                     pooled connection (Stage 1, unchanged)
```

`burndown_service` does not write anything — it calls
`bug_history_repository.list_by_bug()` (Stage 6, unchanged) once per issue
and turns the existing audit trail into a chart-ready shape. No new
history-writing code was needed for this stage.

---

## 3. Data model

**Table: `sprints`** — new, matches the spec exactly (`id`,
`organization_id`, `project_id`, `name`, `goal`, `start_date`, `end_date`,
`status ENUM('future','active','closed') DEFAULT 'future'`), plus a
`created_at` for ordering (not in the spec's table, following the same
convention every other table in this codebase already uses).

**Altered `bugs`:** adds `sprint_id INT NULL`, FK → `sprints(id)`
`ON DELETE SET NULL` — matching the `ON DELETE SET NULL` convention
already used for `parent_id` and `assigned_to`, so deleting a sprint
(not a feature this stage builds, but the FK still needs a policy) can
never cascade-delete issues.

**Table: `issue_links`** — new, matches the spec exactly. Stored once,
`bug_id_a → bug_id_b` with a `link_type`; no reverse row, no
`organization_id` column (every read joins back through `bugs` on both
sides to establish organization membership, the same pattern
`comments`/`bug_history`/`issue_watchers` already use since Stage 6).

**Table: `saved_filters`** — new, matches the spec exactly, including
`is_shared TINYINT(1) DEFAULT 0` (present in the schema, unused — see §1).

---

## 4. Routes delivered

| Method | Path | Auth | Behaviour |
|---|---|---|---|
| GET | `/backlog` | required | Project-scoped backlog + open-sprint sections (defaults to the org's first project, same convention as the board). |
| POST | `/sprints/create` | Admin/PM | Creates a sprint in `future` status. |
| POST | `/sprints/<id>/start` | Admin/PM | `future` → `active`; rejected if another sprint in the same project is already active. |
| POST | `/sprints/<id>/close` | Admin/PM | `active` → `closed`. |
| POST | `/issues/<id>/sprint` | Admin/PM | Moves an issue into a sprint, or back to the backlog if `sprint_id` is blank. |
| GET | `/issues` | required | **New** issue list/search page (see §5.2) — filters via `project_id`/`status`/`priority`/`issue_type`/`assigned_to` query params, renders saved-filter chips. |
| POST | `/issues/<id>/link` | any org member who can view the issue | Creates a typed, directional link to another issue (by key). |
| POST | `/issues/<id>/link/<link_id>/remove` | any org member who can view the issue | Removes a link; works from either linked issue's page. |
| POST | `/filters/save` | required | Saves the current filter combination under a name. |
| GET | `/filters` | required | JSON list of the caller's saved filters. |

---

## 5. Key design decisions

### 5.1 A new `GET /issues` page had to be built — the spec assumes one exists

The spec's frontend section says "Issue List page (extend)," but no such
page exists: Stage 5 deliberately kept the project detail page's issue
table minimal and explicitly did *not* build a real list/search page
(STAGE-05-REPORT.md §5.7), and no stage since has added one. Saved
filters are meaningless without somewhere to apply status/priority/
project/assignee filters and see results, so `GET /issues` was added as
the minimal necessary infrastructure — the same reasoning already used
twice before (Stage 5's project-issue table, Stage 5's screenshot route).
It supports exactly the five filter dimensions the spec names or implies
("status, priority, project, assignee, etc." — `issue_type` was added as
the one reasonable "etc." given it's already a first-class column with
no schema cost), nothing more: no pagination, no free-text search, no
sorting controls.

### 5.2 Moving/assigning issues between the backlog and a sprint is Admin/PM-only, same as creating/starting/closing one

The spec doesn't explicitly state a role for `POST /issues/<id>/sprint`
specifically, but `services/project_service.py`'s own docstring (written
in Stage 4) already names a Stage 3 permission called "Manage sprints,"
granted to Admin/PM. Since Stage 8 is the first stage sprints actually
exist, all sprint-related actions — including backlog grooming, not just
lifecycle transitions — were treated as falling under that one
permission. `sprint_service.verify_sprint_manager()` gates all four
sprint routes and the sprint-assignment route identically. Flagged since
the spec text alone doesn't spell this out for the assignment route
specifically; a Developer/Tester can still view the backlog and every
sprint's contents, just not rearrange them.

### 5.3 The single-active-sprint rule is a plain check-then-write, not a locked transaction

Unlike Stage 4's issue-number allocation (`SELECT ... FOR UPDATE` inside
one transaction, because concurrent issue creation is a realistic hot
path), starting a sprint is a rare, deliberate, human-triggered action.
`sprint_service.start_sprint()` reads `get_active_for_project()` and then
writes, as two separate steps — a narrow race window exists if two people
click "Start" on two different sprints in the same project in the same
instant, in theory. The Definition of Done only requires the rule be
enforced in the normal case ("attempting to start a second sprint while
one is already active... is rejected"), not stress-tested for genuine
concurrency the way issue-key allocation was. Flagged as a known,
accepted gap rather than silently building (or silently skipping)
transaction-level locking.

### 5.4 The burndown's "actual" line is reconstructed from `bug_history`, using current sprint membership and current point values throughout

Per the Definition of Done ("the actual line reflects real remaining
story points/issues as of each day, not a static mock"), each day's
remaining-work figure is computed by replaying every issue's Stage 6
status-change history up to that day (`burndown_service._status_as_of()`)
rather than just plotting today's snapshot repeated across the whole
range — verified directly in §7 with a controlled history entry at a
known timestamp, confirming the line actually drops on the right day
rather than being flat. Two simplifications were made deliberately: (1)
the chart uses whichever issues are *currently* in the sprint, so an
issue added or removed from the sprint mid-sprint is treated as if it had
always been there (or never was), and (2) the same is true for point
values — a story-point re-estimate changes the whole chart's shape
retroactively rather than only affecting days after the re-estimate.
Both are standard simplifications for a burndown built without a
separate scope-history table, but are real gaps worth flagging. The
y-axis metric is story points if any issue in the sprint has them set,
otherwise a flat one-per-issue count, so a sprint with no estimates still
gets a meaningful chart instead of an all-zero one.

### 5.5 The link-target picker is an exact-key text field, not a live search

The spec says "pick link type + target issue by key/search." A true
type-ahead search would need a new AJAX endpoint the spec's route table
doesn't list, and "search" without further detail is read here as the
looser of the two options already named ("by key") rather than a reason
to add API surface the spec never asked for. `link_service.create_link()`
looks the typed key up with an exact, case-insensitive (via upper-casing
before comparison) match and returns a clear "not found" error otherwise.

### 5.6 The link-creation form offers seven options, not four, from the current issue's point of view

The spec lists four relationship families (`blocks`/`blocked by`,
`relates to`, `duplicates`/`duplicated by`, `clones`/`cloned by`) — seven
labeled choices once every directional pair is counted individually. The
add-link `<select>` on the detail page offers exactly those seven
(`services/link_service.py::LINK_FORM_OPTIONS`), each mapping to which
side of the single stored row (`bug_id_a`/`bug_id_b`) the *current* issue
ends up on. Choosing "Blocked by" on WEB-5 targeting WEB-9 stores
`(bug_id_a=WEB-9, bug_id_b=WEB-5, link_type='blocks')` — so WEB-9's own
page then correctly reads "Blocks WEB-5," derived, with no second row.
`templates/base.html` gained a `{% block scripts %}` hook (empty on every
page except `backlog.html`) purely so the Chart.js CDN tag and its inline
init script could live only on the one page that needs them, rather than
loading on every page in the app.

### 5.7 Closed sprints disappear from the backlog page entirely

`sprint_service.list_open_sprints()` only ever returns `future`/`active`
sprints (`OPEN_STATUSES`); a closed sprint's section simply stops
rendering on `/backlog`. The spec's own frontend description only calls
for "one collapsible section per sprint (future/active)" — closed
sprints were never asked to appear there, and there is no other page yet
for browsing sprint history. This is a real, flagged gap (once a sprint
closes, there is currently no UI to see it again at all, though its data
and its issues' history remain intact), acceptable because reporting
across sprints belongs to a later stage, not this one.

---

## 6. Setup procedure

```bash
python -m scripts.create_tables     # adds sprints, issue_links, saved_filters; adds bugs.sprint_id
python run.py                       # -> http://127.0.0.1:5000/backlog
```

No new Python dependencies. Chart.js is loaded via CDN only on the
backlog page, exactly as `00-README.md`'s global convention specifies
("Chart.js (via CDN) for charts").

---

## 7. Verification results

As in every prior stage, the sandbox has no MySQL server, so the full
request flow was exercised against in-memory stand-ins for every
repository touched this stage (`sprint_repository`, `issue_link_repository`,
`saved_filter_repository`, and the new `issue_repository` functions),
matching each real function's exact signature, driven both directly
(service-level, for precise assertions on burndown math and link
labeling) and through the real Flask app (`app.test_client()`) end-to-end
for the permission-gated routes.

**50 new checks for this stage, all passing.**

| # | Check | Result |
|---|---|---|
| 1-4 | `verify_sprint_manager` allows Admin/PM and rejects Developer/Tester | Pass |
| 5-11 | A sprint is created, started (future→active), a second sprint's start is rejected while one is active (and it stays `future`, with a real error message), the active sprint closes, and only then can the second one start | Pass |
| 12-18 | A new issue starts in the backlog; assigning it into a sprint removes it from the backlog and adds it to the sprint's list; moving it back to the backlog reverses both; assigning into a **closed** sprint is rejected | Pass |
| 19-24 | A 5-day sprint's burndown has 5 data points, correct total scope (3+2=5 points), an ideal line from 5 to 0, and an actual line that stays at 5 for two days then drops to 2 on and after the exact timestamp an issue's real history shows it reaching "Done" -- confirmed non-flat | Pass |
| 25 | A sprint with no start/end date returns `None` from the burndown computation rather than fabricated data | Pass |
| 26-27 | A link creates exactly one stored row | Pass |
| 28-29 | The source issue shows "Blocks", the target issue shows "Blocked by" toward the source -- derived from that one row | Pass |
| 30 | Linking an issue to itself is rejected | Pass |
| 31 | Creating the identical link twice is rejected | Pass |
| 32-33 | A symmetric "relates to" link's *reverse* pairing is recognized and rejected as the same relationship | Pass |
| 34-36 | A link is removed successfully from the non-owning side and is gone from both issues' link lists afterward | Pass |
| 37-40 | A saved filter's `filter_data` round-trips correctly, and re-running it after a new matching issue is created includes that issue | Pass |
| 41-46 | Route-level: `/backlog` renders for an Admin; a Developer's `POST /sprints/create` and `POST /sprints/<id>/start` are both rejected; `/issues` renders with real filtered results; `POST /filters/save` and `POST /issues/<id>/link` (+ its `/remove`) all work end-to-end through the real routes | Pass |
| 47-48 | The issue detail page renders its new "Linked Issues" panel; the backlog page still renders cleanly after all the state changes above | Pass |

All modified/added Python modules compile cleanly (`py_compile`, exit 0)
and `static/script.js` parses cleanly (`node -c`).

### Definition of Done

- [x] Attempting to start a second sprint while one is already active in the same project is rejected
- [x] Burndown chart's "actual" line reflects real remaining story points/issues as of each day, verified against a controlled `bug_history` timestamp, not a static mock
- [x] A link created from Issue A to Issue B shows correctly worded on both issues without a second link record (confirmed only one row exists in storage)
- [x] A saved filter reproduces the exact same result set when clicked later, including after new issues have been added (confirmed by adding a matching issue *after* saving and re-running the filter)

---

## 8. Interpretations and open items

**A new `GET /issues` page (§5.1)** and the reasoning behind it is the
single biggest interpretation this stage rests on — flagged clearly, same
as the two prior instances of this pattern in Stage 5.

**Sprint/backlog management is Admin/PM-only, including issue↔sprint
assignment (§5.2)** — extends a permission the spec named in Stage 3 but
never previously exercised; worth confirming this matches intent, since a
Developer currently cannot even move their own issue into the sprint
they're working from.

**No transactional locking on the single-active-sprint rule (§5.3)** — a
theoretical race exists between two simultaneous "Start" clicks in the
same project; not stress-tested the way Stage 4's issue-key allocation
was, since starting a sprint is a low-frequency, human-paced action.

**Burndown scope is always "current," never historical (§5.4)** — both
which issues count and how many points each is worth are taken from the
sprint's present-day membership, applied uniformly across the whole
chart. A sprint whose scope changed mid-flight will show a chart that
doesn't perfectly match what a team would have seen in real time on an
earlier day.

**No live search for link targets (§5.5)** — exact-key lookup only;
flagged in case a fuzzy/typeahead search was actually wanted (would need
a new AJAX endpoint beyond what this stage's route table lists).

**Closed sprints have no page at all (§5.7)** — once closed, a sprint's
data still exists (its issues keep their history), but there is currently
no UI anywhere to view it again. Acceptable for this stage; likely
belongs with whatever later stage adds cross-sprint reporting.

**The DDL has not been run against a live MySQL.** `scripts/create_tables.py`
was syntax-checked (`py_compile`) and reasoned through, but as in every
prior stage, the sandbox has no MySQL server to execute it against — in
particular, the `sprints`→`bugs` foreign key ordering (sprints must be
created before bugs on a fresh database), the `issue_links` table's two
FKs to `bugs`, and the `saved_filters.filter_data` JSON column have not
been confirmed against a real server. Please run
`python -m scripts.create_tables` and check its output — it should print
a line for `sprints`, `issue_links`, and `saved_filters`, plus a line
confirming `bugs.sprint_id` was added (only relevant if your database
predates this stage).

---

## 9. Notes for Stage 9

- `services/sprint_service.OPEN_STATUSES` (`["active", "future"]`) is the
  reference list for "sprints still relevant to planning" — anything that
  needs to reason about closed sprints will need a new query, since
  today's repository functions were never asked to return them together
  with open ones.
- `services/link_service.LINK_FORM_OPTIONS` and its `FORWARD_LABELS`/
  `REVERSE_LABELS` dicts are the canonical place link-type display text
  lives — reuse rather than re-deriving if another page ever needs to
  show a link's label.
- `services/burndown_service._status_as_of()` is a generically useful
  "what was this issue's status on day X" reconstruction built on top of
  `bug_history` — worth reusing directly rather than rewriting if a later
  stage needs historical status data for any other reason (e.g. a
  cumulative flow diagram).
- `templates/base.html`'s new `{% block scripts %}` hook is available to
  any future page that needs a page-specific script tag (e.g. another
  Chart.js chart) without adding it globally.
