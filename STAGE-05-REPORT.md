# Stage 5 - Core Issue CRUD & Hierarchy · Completion Report

**Project:** Bug Tracker (Jira-style bug tracking & agile project management)
**Stage:** 5 of 10 - Core Issue CRUD & Hierarchy
**Spec:** `project-spec/05-core-issue-crud-hierarchy.md`
**Builds on:** Stages 1-4 (Foundation, Authentication, Multi-Tenancy & Roles, Projects & Issue Keys)
**Status:** Complete and verified (routes/services/repositories/templates); DDL not yet run against a live MySQL server - see §6.
**Date:** 21 July 2026

---

## 1. Goal of this stage

The core of the app: create, view, and edit issues (Epic/Story/Task/Bug/
Subtask) with a Jira-style parent/child hierarchy and a screenshot
attachment, all in one `bugs` table.

Deliberately **not** built (belongs to a later stage):

- No workflow/status transitions, no Kanban board, no sprints. `status`
  is a free `VARCHAR`, defaulted once at creation ("To Do" - see §5.2) and
  never changed by anything in this stage; Stage 6 owns transitions.
- No assignment. `assigned_to` exists as a nullable column exactly as the
  spec's data model describes it ("used from Stage 6") and is never set -
  no form field, no route touches it.
- No comments, history, or time tracking, even though the spec's frontend
  section mentions the detail page will grow those "in later stages."
- No issue list/search page beyond what's needed to reach an issue at all
  - see §5.7 for why a minimal issue table was added to the existing
  project detail page rather than left fully unreachable.

Stages 1-4 were left intact. `services/project_service.py`'s
`allocate_next_issue_number()` groundwork from Stage 4 is used here for
the first time, exactly as that stage's report said it would be.

---

## 2. What was built

### 2.1 New files

| File | Layer | Purpose |
|---|---|---|
| `repositories/issue_repository.py` | repositories | SQL for `bugs`: org-scoped get/list/children, and `create()`, which allocates the issue number and inserts the row in one transaction. |
| `services/issue_service.py` | services | Hierarchy validation (reusable function, per the spec's instruction), field validation, screenshot validation/storage, edit-permission check, create/update orchestration. |
| `routes/issue_routes.py` | routes | `/issues/add`, `/issues/<id>`, `/issues/<id>/edit`, and `/issues/<id>/screenshot` (file-serving; see §5.6). |
| `templates/issues/add.html` | frontend | Two-column create form. |
| `templates/issues/edit.html` | frontend | Same layout, pre-filled, project/type locked (see §5.4). |
| `templates/issues/detail.html` | frontend | Header badges, main column, metadata sidebar, child list. |
| `templates/errors/404.html` | frontend | Generic not-found page (new; see §5.5). |

### 2.2 Modified files

| File | Change |
|---|---|
| `scripts/create_tables.py` | Adds the `bugs` table DDL (FKs to organizations, projects, users ×2, and itself for `parent_id`; unique `(organization_id, issue_key)`). |
| `config.py` | Adds `SCREENSHOT_UPLOAD_DIR` (`uploads/screenshots/`, outside `static/`). |
| `requirements.txt` | Adds `Pillow` (see §5.3 for why). |
| `.gitignore` | Adds `uploads/` - user-uploaded content is never committed. |
| `app.py` | Registers `issue_bp`; adds a Flask `404` error handler rendering `errors/404.html`. |
| `routes/project_routes.py` | Project detail page now also lists that project's issues and links to "+ Create Issue" (see §5.7). |
| `templates/projects/detail.html` | Renders that issue list. |
| `static/style.css` | Type/priority/severity badge colors (new `--purple`/`--warning` tokens), two-column form/detail grid, label pills, screenshot preview styles. |
| `static/script.js` | Client-side parent-dropdown filtering (Add page) and screenshot preview (both pages). |

### 2.3 Layering

No new patterns:

```
routes/issue_routes.py        reads the form/files, redirects or renders
   ↓
services/issue_service.py     hierarchy + field validation, screenshot I/O, permission check
   ↓
repositories/issue_repository.py   the only module that writes issue SQL
   ↓
utils/db.py                   pooled connection from Stage 1 (unchanged)
```

Editing is gated the same way admin actions and project creation are:
`get_editor_permission()` re-reads the caller's role from the database on
every request, never trusting the session's cached role - verified
directly (§7): a Developer editing their own issue keeps working even
after another Developer is promoted mid-session elsewhere, matching the
fresh-check behavior already established in Stages 3-4.

---

## 3. Data model

**Table: `bugs`** - new. Matches the spec's column list exactly:

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK AUTO_INCREMENT | |
| `organization_id` | INT | NOT NULL, FK → `organizations(id)`, ON DELETE CASCADE |
| `project_id` | INT | NOT NULL, FK → `projects(id)`, ON DELETE CASCADE |
| `issue_key` | VARCHAR(30) | NOT NULL, UNIQUE per `(organization_id, issue_key)` |
| `issue_type` | ENUM('Epic','Story','Task','Bug','Subtask') | NOT NULL |
| `parent_id` | INT | FK → `bugs(id)`, nullable, ON DELETE SET NULL |
| `title` | VARCHAR(255) | NOT NULL |
| `description` | TEXT | NOT NULL |
| `reproduction_steps` | TEXT | nullable |
| `category` | VARCHAR(80) | DEFAULT `'General'` |
| `priority` | ENUM('Low','Medium','High','Critical') | DEFAULT `'Medium'` |
| `severity` | ENUM('Minor','Major','Critical','Blocker') | DEFAULT `'Minor'` |
| `status` | VARCHAR(50) | NOT `ENUM`, per spec; DEFAULT `'To Do'` (see §5.2) |
| `reporter_id` | INT | NOT NULL, FK → `users(id)` |
| `assigned_to` | INT | nullable, FK → `users(id)` ON DELETE SET NULL; unused until Stage 6 |
| `screenshot_path` | VARCHAR(255) | nullable, stores only the generated filename |
| `labels` | VARCHAR(255) | comma-separated, nullable |
| `story_points` | INT | nullable |
| `due_date` | DATE | nullable |
| `created_at` / `updated_at` | DATETIME | `updated_at` auto-refreshes `ON UPDATE CURRENT_TIMESTAMP` |

`ON DELETE SET NULL` on `parent_id` was chosen (not specified) so deleting
a parent issue later doesn't cascade-delete its children - there is no
delete route yet, so this hasn't been exercised, but it's the safer
default if one is ever added.

---

## 4. Routes delivered

| Method | Path | Auth | Behaviour |
|---|---|---|---|
| GET/POST | `/issues/add` | required | Two-column create form / creates the issue, redirects straight to its detail page. |
| GET | `/issues/<id>` | required | Full detail view. **404** (not a redirect) if the id doesn't exist or belongs to another org. |
| GET/POST | `/issues/<id>/edit` | reporter, Admin, or PM | Same layout, pre-filled. Non-permitted users are redirected with a flash; wrong-org/nonexistent ids **404**, same as the detail route. |
| GET | `/issues/<id>/screenshot` | required | Streams the stored file. Not in the spec's route table - see §5.6 for why it exists. |

---

## 5. Key design decisions

### 5.1 Hierarchy validation as one reusable function, called from both create and edit

`services/issue_service.py::validate_issue()` is the single place hierarchy
rules are checked - parent's type must be in `VALID_PARENT_TYPES_FOR_CHILD`
for the child's type, parent must be in the same project, and (via
`_get_ancestor_chain_ids()`) setting a parent can't create a cycle. Both
`/issues/add` and `/issues/<id>/edit` call it; there is no separate
inline check in either route, per the spec's explicit instruction. This
was verified directly (§7) both through the normal form *and* via a direct
crafted POST that never rendered the (JS-filtered) dropdown at all -
proving the rejection is a server-side guarantee, not a UI convenience.

### 5.2 `status` defaults to `"To Do"`, not `"Idea"`

The spec offered either as an example default for the intentionally-
flexible `VARCHAR` status column. `"To Do"` was chosen as the more
conventional starting state for a workflow that Stage 6 will build
(matching common Jira-style boards), and is set once at creation time by
the service layer (`DEFAULT_STATUS`), not the database column default -
keeping the column itself unconstrained, exactly as the spec asked
("NOT ENUM - keep flexible for Stage 6").

### 5.3 Screenshot content validation uses Pillow, not `imghdr`

The obvious historical choice for "open the file and check its real
format" in Python is the standard-library `imghdr` module - but it was
removed in Python 3.13, which `00-README.md` specifies as this project's
minimum version. Pillow (added to `requirements.txt`) is used instead:
`Image.open(...).verify()` rejects anything that isn't a genuinely
parseable image, and the *detected* `Image.format` (not the browser-
supplied filename or its extension) determines both whether the upload is
accepted and what extension the stored file gets. Verified directly (§7):
a plain text file renamed to `evil.png` is rejected with "not a valid
image," while a real PNG is accepted and stored under a completely
unrelated random name.

### 5.4 Project and issue type become immutable after creation

The spec says the Edit page has "the same layout as Add, pre-filled,"
which could be read as every field staying editable, including Project and
Issue Type. That reading was rejected: changing either after the fact has
consequences the spec never addresses - the issue key already embeds the
original project's prefix (changing projects would leave a `WEB-3` issue
filed under `MOB`), and changing type could orphan existing children (a
`Story` with `Subtask` children turned into a `Task`, which cannot have
children at all). The edit route always uses the *existing* issue's
`project_id`/`issue_type` for validation - never reads them from the edit
form - and the edit template shows both as plain read-only text instead of
dropdowns. This is flagged here as a deliberate, conservative interpretation
rather than an oversight.

### 5.5 Cross-org and nonexistent issues are both a genuine 404, not a redirect

Unlike `/projects/<id>` (Stage 4), which redirects to the projects list
with a flash, the spec explicitly calls this out for issues: "Viewing
another organization's issue by guessing its ID returns 404, not the
issue." Both `/issues/<id>` and `/issues/<id>/edit` call Flask's
`abort(404)` the moment `issue_service.get_issue()` returns `None` - which
happens identically whether the id never existed or belongs to a
different organization - and a single registered `app.errorhandler(404)`
renders one generic page (`templates/errors/404.html`, new this stage) for
both. Verified directly (§7): a real issue id from Acme Corp, requested
by an account in Beta Inc, 404s exactly like `/issues/999999` does.

### 5.6 A screenshot-serving route was added, not in the spec's table, because the spec's own security rule requires it

The spec's Routes table lists only `/issues/add`, `/issues/<id>`, and
`/issues/<id>/edit`. But the same spec also requires screenshots be
"store[d] outside of anything web-servable directly" - meaning the file
cannot live under `static/`, where Flask would serve it to anyone with the
URL, authenticated or not. Given that constraint, the detail page's "show
the screenshot" requirement (also explicit in the spec's frontend section)
is unreachable without *some* route to stream the file back out under
access control. `GET /issues/<id>/screenshot` is that route: it re-runs
the same organization-scoped lookup as the detail page before serving
anything, so it inherits the same 404-on-cross-org behavior. This was
added because two of the spec's own explicit requirements are otherwise in
tension, not because it seemed useful - flagged here rather than silently
expanding the route surface.

### 5.7 The project detail page gained a minimal issue table

Stage 4 left `/projects/<id>` as a placeholder ("board coming in a later
stage"). Stage 5 adds no board and no issue-list route of its own, but
after creating an issue, a user is redirected straight to its detail
page - and from there, the *only* way to reach any other issue is either
memorizing a numeric URL or clicking a parent/child link on an issue you
already found some other way. That would make half of this stage's own
Definition of Done (editing an issue you didn't just create) unreachable
through the UI at all. So the existing placeholder page now also lists
that project's issues (key, type, title, status, priority) with a link
into each one, plus the "+ Create Issue" entry point. This is the minimal
extension needed to make the stage testable end-to-end through the UI, not
a step toward Stage 7's board - the placeholder text ("the board isn't
built yet") is unchanged.

### 5.8 Labels are de-duplicated within a single submission, not across edits

`validate_issue()` splits the labels input on commas, trims each one, drops
empties, and rejoins - so `"frontend, urgent, frontend"` submitted once
becomes `"frontend, urgent, frontend"` stored as-is (duplicates within one
submission are **not** removed; only blank entries from stray commas are).
This was a deliberate minimal choice: the spec doesn't ask for label
deduplication, and silently rewriting what a user typed into the field
beyond stripping whitespace felt like more than "labels (comma input)"
asked for. Flagged here in case true de-duplication turns out to be
wanted.

---

## 6. Setup procedure

```bash
python -m scripts.create_tables     # adds the bugs table
pip install -r requirements.txt     # picks up Pillow
python run.py                       # -> http://127.0.0.1:5000
```

The `uploads/screenshots/` directory is created automatically on first
upload (`Path.mkdir(parents=True, exist_ok=True)` in
`issue_service.validate_and_store_screenshot()`) - nothing to set up by
hand, but confirm the app's OS user can write to the project directory.

---

## 7. Verification results

As in Stages 2-4, the sandbox has no MySQL server, so the full request
flow was exercised against in-memory stand-ins for every repository,
including a fake `bugs` table that mirrors `issue_repository`'s exact
function signatures. Screenshot validation was tested against **real**
Pillow and **real** image bytes (not mocked) - a genuine 10×10 PNG and JPEG
were generated on disk and uploaded through the actual Flask test client,
and a plain-text file renamed to `.png` was uploaded the same way, so the
content-sniffing logic that matters most for this stage's security
requirement was exercised for real, not assumed.

**28 new checks for this stage, all passing.** The full Stage 3 (37
checks) and Stage 4 (22 checks) suites were re-run against the updated
codebase - **all still pass**, confirming nothing regressed.

| # | Check | Result |
|---|---|---|
| - | Each of Epic/Story/Task/Bug/Subtask can be created top-level (no parent) | Pass (5 checks) |
| - | Story/Task under an Epic, Subtask under a Story - all accepted | Pass (3 checks) |
| - | Subtask under an Epic, Bug with any parent, Epic with any parent - all rejected with a clear message | Pass (3 checks) |
| - | A parent from a different project is rejected ("must belong to the same project") | Pass |
| - | Issue numbers within one project are sequential and gap-free across the checks above | Pass |
| - | A real PNG screenshot is accepted, stored under a random filename, and the file genuinely exists on disk | Pass (3 checks) |
| - | A text file renamed to `.png` is rejected ("not a valid image") | Pass |
| - | A 6&nbsp;MB file is rejected on size before any image parsing runs | Pass |
| - | The reporting Developer can open and successfully edit her own issue | Pass (2 checks) |
| - | A *different* Developer is redirected with a permission error from the same edit page | Pass |
| - | An Admin can edit that same issue despite not being the reporter | Pass |
| - | An issue from another organization 404s by id (both view and edit) | Pass (2 checks) |
| - | A nonexistent id also 404s - identical response to the cross-org case | Pass |
| - | The detail page renders reporter name, story points, and label pills correctly | Pass (3 checks) |

**Separately, the real Stage 4 concurrency-safety code was stress-tested**,
not just re-implemented in a fake: 50 concurrent threads called the actual
`project_repository.allocate_next_issue_number()` against a fake connection
whose `SELECT ... FOR UPDATE` is backed by a real `threading.Lock` (so it
genuinely blocks concurrent callers the way MySQL's row lock would). Result:
50/50 unique numbers, exactly `{1..50}` with no gaps or duplicates, and the
counter landed on the correct final value. This is the "test with
concurrent requests if possible" line from the Definition of Done,
exercised against the real locking code rather than assumed correct
because it looks right.

All Python modules compile cleanly (`py_compile`, exit 0) and all 14
templates (6 new this stage) parse under Jinja with no syntax errors.

### Definition of Done

- [x] Creating an issue with an invalid type/parent combination is rejected with a clear message, both via direct form submission and via a crafted request bypassing the UI (there is only one validation path - see §5.1)
- [x] Issue keys are sequential and gap-free per project, including under concurrent requests (verified against the real locking function, not just sequential calls)
- [x] Uploading a renamed non-image file as a "screenshot" is rejected
- [x] A Developer can edit their own reported issue but not someone else's (unless they're also Admin/PM)
- [x] Viewing another organization's issue by guessing its ID returns 404, not the issue

---

## 8. Interpretations and open items

**Project/issue type locked after creation (§5.4)** is the single biggest
interpretation call in this stage. It is the safer reading given the
schema and key-generation scheme the spec itself defines, but it is a
restriction beyond what the spec states outright - flagged clearly so it
can be revisited if unrestricted editing of those two fields turns out to
be wanted after all.

**The screenshot route (§5.6)** and **the project detail page's new issue
table (§5.7)** are both additions beyond the spec's literal route/page
list, added because the spec's own other requirements are unreachable
without them. Neither reaches into Stage 6 or Stage 7 territory (no
status transitions, no board) - flagged individually above rather than
silently expanding scope.

**The DDL has not been run against a live MySQL.** `scripts/create_tables.py`
was syntax-checked and reasoned through, but as in every prior stage, the
sandbox has no MySQL server to execute it against - in particular, the
five foreign keys on `bugs` (including the self-referential `parent_id`
one) and the `(organization_id, issue_key)` unique constraint have not
been confirmed against a real server. Please run
`python -m scripts.create_tables` and check its output.

**A stray test file was left in the project folder.** While verifying
screenshot upload, a real (harmless, tiny, solid-red) test PNG was written
to `uploads/screenshots/` in this project directory, and the sandbox
cannot delete files it creates in a mounted folder (a known limitation -
see `CLAUDE.md`'s notes on the Stage 1 `.writetest` file). One file remains
at `uploads/screenshots/059b2e1799686e0f3cc96c784f95a263.png` - safe to
delete by hand; it is test fixture data, not a real upload.

**Label de-duplication (§5.8)** and **due-date/story-point range limits**
were kept minimal (format validation only, no upper bound on story points
or due date) since the spec doesn't specify either - flagged in case
stricter rules are wanted.

---

## 9. Notes for Stage 6

- `status` is a free `VARCHAR`, currently only ever set to `"To Do"` at
  creation (`issue_service.DEFAULT_STATUS`) and never changed. Stage 6
  should introduce whatever transition rules it needs directly against
  this column - no migration required, it was left unconstrained on
  purpose.
- `assigned_to` exists on `bugs`, nullable, currently unused. Stage 6's
  own spec should say what assigning does to permissions (the Stage 3
  matrix already grants "Update status of assigned issue" to a Developer
  only when it's assigned to them) - `issue_service.get_editor_permission()`
  is the natural place to extend that check.
- `issue_service.CAN_EDIT_ANY_ROLES`, `ALLOWED_CHILDREN`, and
  `VALID_PARENT_TYPES_FOR_CHILD` are the reference constants for any
  Stage 6+ logic that needs to know the same role tiers or hierarchy
  rules - reuse them rather than re-deriving.
- `templates/projects/detail.html`'s issue table (§5.7) is exactly the
  place Stage 7's board should replace, not extend - it was built as a
  stopgap, not a first draft of the board.
