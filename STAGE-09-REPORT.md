# Stage 9 - Extensibility · Completion Report

**Project:** Bug Tracker (Jira-style bug tracking & agile project management)
**Stage:** 9 of 10 - Extensibility
**Spec:** `project-spec/09-extensibility.md`
**Builds on:** Stages 1-8 (Foundation, Authentication, Multi-Tenancy & Roles, Projects & Issue Keys, Core Issue CRUD & Hierarchy, Workflow & Status, Kanban Board, Agile Planning)
**Status:** Complete and verified (routes/services/repositories/templates); DDL not yet run against a live MySQL server - see §6.
**Date:** 22 July 2026

---

## 1. Goal of this stage

Let each organization tailor the tool without code changes: project-specific
custom fields, if-this-then-that automation rules, time tracking and
release versions.

Deliberately **not** built (belongs to a later stage or out of scope):

- No automation rule **edit** route/UI. The spec's routes table lists only
  list/create/toggle/delete for `/automation`; the frontend section's prose
  mentions "edit/delete" as two card actions, but adding a full edit route
  and form beyond what the routes table specifies would be scope creep in
  the direction Stage 8 explicitly warned against (see its own §5.1
  precedent, used the other way here: not adding surface the route table
  doesn't list). A rule can be disabled and a fresh one created instead;
  flagged in §8 in case editing was actually wanted.
- No free-text/typeahead condition-field picker. A condition's `field` is a
  plain text input (e.g. `new_status`, `priority`, `field_name`) rather than
  a dropdown of known keys, since the set of valid fields depends on which
  trigger is selected and the spec doesn't ask for that cross-referencing
  UI - the hint text under the field explains the convention instead.
- No per-project custom-field reordering UI. `display_order` exists and is
  respected on read (fields render and validate in that order), but is only
  ever set once, at creation time, auto-incrementing - the spec's frontend
  section doesn't describe a reorder control.
- `versions.description` remains permanently unpopulated via the UI - same
  interpretation Stage 8 made for `saved_filters.is_shared` (§1 of that
  report): the column exists exactly as the spec's data model defines it,
  `version_repository.create()` accepts it, but the "+ New Version" form
  only has Name and Release Date, matching the spec's own frontend section.
- No changes to Stage 7's board columns or Stage 8's burndown - automation
  now fires from the board's drag-and-drop move, but nothing about how the
  board itself renders or groups issues changed.

Stages 1-8 were left intact. Pre-existing files touched: `scripts/create_tables.py`
(new tables + three altered `bugs` columns), `app.py` (three new blueprints,
no route logic), `templates/base.html` (two new sidebar links),
`repositories/issue_repository.py` (`_COLUMNS`/`create`/`update` extended,
two new functions - nothing existing removed), `services/issue_service.py`
(`validate_issue`/`create_issue`/`update_issue` extended with fix-version
handling), `routes/issue_routes.py` (custom-field + fix-version + automation
wiring added to `add_issue`/`edit_issue`/`change_status`/`assign_issue`,
plus two new routes), `routes/board_routes.py` (`move_issue` now fires
automation), `templates/issues/add.html`/`edit.html`/`detail.html` (new
fields, sections), `templates/projects/detail.html` (one new button),
`static/style.css`/`static/script.js` (new sections only).

---

## 2. What was built

### 2.1 New files

| File | Layer | Purpose |
|---|---|---|
| `repositories/custom_field_repository.py` | repositories | SQL for `custom_field_definitions`/`custom_field_values`: definition CRUD, `count_definitions` (for auto-assigning `display_order`), `set_value` (upsert), `list_values_for_issue` (LEFT JOIN so a field added after issue creation still appears, blank). |
| `repositories/automation_repository.py` | repositories | SQL for `automation_rules`, including `list_matching` - the automation engine's one read query. JSON (de)serialization of `conditions`/`actions` happens here, same convention as Stage 8's `saved_filter_repository`. |
| `repositories/time_entry_repository.py` | repositories | SQL for `time_entries`: `create`, `list_by_bug` (chronological ascending). |
| `repositories/version_repository.py` | repositories | SQL for `versions`: CRUD, `name_exists` (pre-check for the `UNIQUE(project_id, name)` constraint), `set_status`. |
| `services/custom_field_service.py` | services | Definition validation/CRUD, the Admin/PM `verify_field_manager` gate and per-issue value validation/persistence (`save_values` returns which fields actually changed, for the `field_updated` trigger). |
| `services/automation_service.py` | services | Rule validation/CRUD, display-summary helpers and `execute_automation_rules()` - the automation engine itself. |
| `services/time_tracking_service.py` | services | Log-time validation, `total_spent()` (always summed fresh from entries, never cached), estimate validation. |
| `services/version_service.py` | services | Version validation/CRUD, the Admin/PM `verify_version_manager` gate, visible-vs-selectable version lists, release/archive transitions. |
| `routes/field_routes.py` | routes | `GET/POST /projects/<id>/fields`, `POST /projects/<id>/fields/<id>/delete`, `GET /api/fields?project_id=`. |
| `routes/automation_routes.py` | routes | `GET/POST /automation`, `POST /automation/<id>/toggle`, `POST /automation/<id>/delete`. |
| `routes/version_routes.py` | routes | `GET/POST /versions`, `POST /versions/<id>/release`, `POST /versions/<id>/archive`, `GET /api/versions?project_id=`. |
| `templates/projects/fields.html` | frontend | Field list (type, required, delete) + "+ Add Field" form with conditional Options textarea. |
| `templates/automation/list.html` | frontend | Rule cards (scope/trigger/condition/action summaries, enable toggle, delete) + "+ New Rule" form with a dynamic condition builder and action-specific fields. |
| `templates/versions/list.html` | frontend | One table per project: name, release date, status badge, open/resolved/total counts, Release/Archive buttons, "+ New Version" form. |

### 2.2 Modified files

| File | Change |
|---|---|
| `scripts/create_tables.py` | Adds `versions`, `custom_field_definitions`, `custom_field_values`, `automation_rules`, `time_entries` DDL; adds `bugs.time_estimate`/`time_remaining`/`fix_version_id` (+ FK) for new databases and a new idempotent `_ensure_bugs_stage9_columns()` migration for existing ones; reorders `STATEMENTS` so `versions` and `custom_field_definitions` precede `bugs` (both are FK targets from `bugs`) and `custom_field_values`/`automation_rules`/`time_entries` follow it. |
| `repositories/issue_repository.py` | `_COLUMNS` gains `time_estimate, time_remaining, fix_version_id`; `create()`/`update()` gain a `fix_version_id` parameter; adds `update_estimate()`, `count_by_fix_version()`. Nothing existing removed. |
| `services/issue_service.py` | `validate_issue()` gains a `fix_version_raw` parameter (validated against `version_repository`, must belong to the issue's own project); `create_issue()`/`update_issue()` pass `fix_version_id` through. Nothing else touched. |
| `routes/issue_routes.py` | `add_issue()` now validates + persists custom field values and fires `issue_created` after a successful create; `edit_issue()` does the same for edits and fires `field_updated` per changed field; `change_status()` and `assign_issue()` fire `status_changed` (the latter only when the auto-transition actually changed status); `issue_detail()` passes custom field values, time-tracking data and the resolved fix-version row; two new routes, `POST /issues/<id>/time` and `POST /issues/<id>/estimate`. |
| `routes/board_routes.py` | `move_issue()` fires `status_changed` automation after a successful drag-and-drop move - the same trigger the detail page's status dropdown fires, so a rule can't be silently bypassed by using the board instead. |
| `app.py` | Registers `field_bp`, `automation_bp`, `version_bp`. |
| `templates/base.html` | Adds "Versions" (everyone) and "Automation" (Admin/PM only) sidebar links. |
| `templates/projects/detail.html` | Adds a "Custom Fields" button (Admin/PM only) next to "+ Create Issue". |
| `templates/issues/add.html` | Adds a Fix Version `<select>` and a custom-fields container, both populated via AJAX when the Project field changes. |
| `templates/issues/edit.html` | Adds a Fix Version `<select>` (server-rendered, since an issue's project can't change) and server-rendered custom-field inputs pre-filled with the issue's current values. |
| `templates/issues/detail.html` | Adds a Fix Version row to the metadata list, a "Custom Fields" card and a "Time Tracking" card (stats row, estimate form, log-time form, entry list). |
| `static/style.css` | New "extensibility (Stage 9)" section: custom-field form spacing, time-tracking stats/entries, automation condition rows/rule cards, version status badges. |
| `static/script.js` | Adds `initNewFieldToggle`/`initFieldTypeOptionsToggle` (fields page), `initNewRuleToggle`/`initConditionRows`/`initActionTypeFields` (automation page), `initNewVersionToggle` (versions page) and `initDynamicFieldsAndVersions` (Add Issue page's AJAX field/version loading). |

### 2.3 Layering

```
routes/field_routes.py
routes/automation_routes.py
routes/version_routes.py
routes/issue_routes.py (extended)      -- fires automation at the end of create/status/assign
routes/board_routes.py (extended)      -- fires automation at the end of a successful move
   ↓
services/custom_field_service.py       definition CRUD, per-issue value validation/persistence
services/automation_service.py         rule CRUD + execute_automation_rules() (the engine)
services/time_tracking_service.py      log-time/estimate validation, total_spent()
services/version_service.py            version CRUD, visibility rules, release/archive
services/issue_service.py (extended)   fix-version validation only
   ↓
repositories/custom_field_repository.py, automation_repository.py,
repositories/time_entry_repository.py, version_repository.py,
repositories/issue_repository.py (extended)
   ↓
utils/db.py                            pooled connection (Stage 1, unchanged)
```

`execute_automation_rules(organization_id, project_id, trigger_event, context, actor_user_id)`
is the single function every issue-mutating route calls, per the spec's own
design note. It never calls back into `workflow_service`'s permission-gated
wrappers (`can_update_status`, `can_assign`) - a rule's own creation by an
Admin/PM is its authority, so its actions (`_run_transition_status`,
`_run_assign`, `_run_action`'s `add_comment`/`assign_to_role` branches) write
directly through `issue_repository`/`bug_history_repository`/`comment_repository`,
while still recording full `bug_history` rows so automated changes are
exactly as auditable as manual ones.

---

## 3. Data model

**Table: `versions`** - new, matches the spec exactly (`id`,
`organization_id`, `project_id`, `name`, `description`, `release_date`,
`status ENUM('unreleased','released','archived') DEFAULT 'unreleased'`),
plus `created_at` and `UNIQUE(project_id, name)`.

**Table: `custom_field_definitions`** - new, matches the spec exactly
(`id`, `organization_id`, `project_id`, `name`,
`field_type ENUM('text','number','date','dropdown','checkbox')`,
`options` JSON, `required` bool, `display_order`), plus `created_at`.

**Table: `custom_field_values`** - new, matches the spec exactly (`id`,
`bug_id`, `field_id`, `value` TEXT), `UNIQUE(bug_id, field_id)`,
`ON DELETE CASCADE` on `field_id` - this FK is what satisfies "deleting a
field cascades to delete its stored values" (Definition of Done #1) without
any application-code deletion loop.

**Table: `automation_rules`** - new, matches the spec exactly (`id`,
`organization_id`, `project_id` NULL-able, `name`,
`trigger_event ENUM('issue_created','status_changed','field_updated')`,
`conditions` JSON, `actions` JSON, `enabled` bool), plus `created_at`.

**Table: `time_entries`** - new, matches the spec exactly (`id`, `bug_id`,
`user_id`, `hours_spent DECIMAL(10,2)`, `description`, `logged_at`).

**Altered `bugs`:** adds `time_estimate DECIMAL(10,2) NULL`,
`time_remaining DECIMAL(10,2) NULL`, `fix_version_id INT NULL` with
`FOREIGN KEY → versions(id) ON DELETE SET NULL` - same "never cascade-delete
an issue over an unrelated row disappearing" policy Stage 8 used for
`sprint_id`.

---

## 4. Routes delivered

| Method | Path | Auth | Behaviour |
|---|---|---|---|
| GET/POST | `/projects/<id>/fields` | Admin/PM | List a project's custom fields; create a new one. |
| POST | `/projects/<id>/fields/<id>/delete` | Admin/PM | Deletes a definition; values cascade via the FK. |
| GET | `/api/fields?project_id=` | required | JSON field list for the Add/Edit Issue form's dynamic loading. |
| GET/POST | `/automation` | Admin/PM | List every org rule (any scope); create a new one. |
| POST | `/automation/<id>/toggle` | Admin/PM | Flips `enabled`. |
| POST | `/automation/<id>/delete` | Admin/PM | Deletes a rule. |
| POST | `/issues/<id>/time` | any org member who can view the issue | Logs a time entry (hours + optional description). |
| POST | `/issues/<id>/estimate` | same as editing the issue (Admin/PM, or the issue's own reporter) | Updates original/remaining estimate. |
| GET/POST | `/versions` | GET: required · POST: Admin/PM | Lists every project's versions with issue counts; creates a new one. |
| POST | `/versions/<id>/release` | Admin/PM | `unreleased` → `released`. |
| POST | `/versions/<id>/archive` | Admin/PM | Any non-archived status → `archived`; hides it from the main list only. |
| GET | `/api/versions?project_id=` | required | JSON selectable-version list for the Add Issue form's Fix Version dropdown. |

---

## 5. Key design decisions

### 5.1 The automation engine bypasses `workflow_service`'s permission gates by design, not oversight

`execute_automation_rules()` never calls `workflow_service.can_update_status`
or `can_assign` before acting - those functions ask "may *this specific
human* do this *right now*," a question that doesn't apply to a rule a
verified Admin/PM already configured in advance. Its actions write straight
through the repository layer instead (`_run_transition_status`, `_run_assign`),
while still recording the same `bug_history` rows a human-driven change
would, so nothing about automation is less auditable, only less
permission-checked at the moment it fires (correctly - the permission check
already happened when the rule was created).

### 5.2 Automated changes are attributed to the user whose action triggered them, not a synthetic "System" account

There is no "System" user row anywhere in this codebase and inventing one
felt like scope beyond what the spec describes. Every automation action
receives `actor_user_id` - the human who created the issue, changed its
status, or dragged its board card - and every resulting `bug_history` row
or comment is written under that person's id. A history entry that reads
"Alice changed status from To Do to In Progress" followed immediately by
"Alice assigned to Dana" (the second one automation-driven) is intentional:
from an audit standpoint, Alice's action is what caused both.

### 5.3 `field_updated` fires only from the edit flow and only for custom fields, not every possible standard-field change

The spec names three triggers without enumerating exactly what counts as a
"field" for `field_updated`. A general diff-every-column engine covering
`title`/`priority`/`description`/etc. isn't described anywhere in the
feature list or Definition of Done, so this trigger was scoped to the one
new kind of field this stage itself introduces: `custom_field_service.save_values()`
already has to compare old vs. new values to know what to persist, so
returning that diff and firing one `field_updated` event per changed custom
field was the natural, minimal reading. It does not fire on issue creation
(there is nothing to have "changed" yet - `issue_created` already covers
that moment).

### 5.4 Board drag-and-drop fires the same `status_changed` trigger the detail page's status dropdown does

Stage 7's board and the detail page's `POST /issues/<id>/status` both
change `bugs.status` and a rule scoped to "on status change, do X" would be
silently unreliable if it only fired from one of the two entry points. Both
`routes/issue_routes.py::change_status` and `routes/board_routes.py::move_issue`
now call `execute_automation_rules()` identically after a successful,
actually-different status change (a no-op status "change" - dropping a card
back into the column it started in - fires nothing, in both places, since
`workflow_service.change_status()` treats that as a no-op and neither route
proceeds to fire the trigger).

### 5.5 `assign_issue`'s auto-transition fires `status_changed` only when it actually changed status

Assigning a developer to a "To Do" issue auto-transitions it to
"In Progress" (a Stage 6 rule); reassigning an already-"In Progress" issue
does not touch status at all. `routes/issue_routes.py::assign_issue` compares
the issue's status before and after the call and only fires `status_changed`
automation when they differ - a rule that says "when status becomes
In Progress, do X" should not fire on every reassignment, only the ones
that actually cross that boundary.

### 5.6 The Add Issue form's Fix Version and Custom Fields both load via AJAX; the Edit Issue form renders both server-side instead

An issue's project can change on the Add form (the user is still choosing
it) but never changes after creation (Stage 5's rule, unchanged). So Add
needs `/api/fields`/`/api/versions` calls that re-fire whenever the Project
`<select>` changes - mirroring the existing `initParentFilter` AJAX-adjacent
pattern already on that page - while Edit can simply render both,
pre-filled with the issue's current project's fields/versions and current
values, once, at page load, with no client-side reactivity needed at all.

### 5.7 No automation rule "edit" route was added

The spec's routes table for `/automation` lists exactly list/create/toggle/delete.
Its frontend prose separately says each rule card has "edit/delete," but
adding a full edit form and route means inventing backend surface the
routes table doesn't specify - the same category of judgment call Stage 8
made in the *other* direction (adding `GET /issues` because saved filters
were meaningless without it). Here, toggling a rule off and creating a
replacement covers the same practical need without exceeding the documented
routes. Flagged in §8 as the interpretation most worth double-checking.

### 5.8 A custom field's condition-field input is free text, not a dropdown of known keys

`automation_service._conditions_pass()` evaluates a condition against a
flattened dict of the issue's own columns plus whatever trigger-specific
keys the calling route supplied (`new_status`/`old_status` for
`status_changed`, `field_name`/`old_value`/`new_value` for `field_updated`).
Which keys are actually meaningful depends on which trigger is selected and
building a picker that cross-references trigger → valid-field-names wasn't
asked for by the spec. The form's hint text names the common cases instead
(`status`, `priority`, `new_status`, `field_name`); an unrecognized field
name simply never matches (`eval_context.get(...)` returns `None`, which
never equals anything typed into "value"), so a typo produces "rule never
fires," not an error - a safe failure mode.

---

## 6. Setup procedure

```bash
python -m scripts.create_tables     # adds versions, custom_field_definitions, custom_field_values,
                                     # automation_rules, time_entries; adds bugs.time_estimate/
                                     # time_remaining/fix_version_id
python run.py                       # -> http://127.0.0.1:5000
```

No new Python dependencies.

---

## 7. Verification results

As in every prior stage, the sandbox has no MySQL server, so the full
request flow was exercised against in-memory stand-ins for every repository
touched this stage (`custom_field_repository`, `automation_repository`,
`time_entry_repository`, `version_repository` and the extended
`issue_repository`/`bug_history_repository`/`comment_repository`), each
matching its real function's exact signature, driven end-to-end through the
real Flask app (`app.test_client()`), including the CSRF check and every
permission gate.

**32 checks for this stage, all passing.**

| # | Check | Result |
|---|---|---|
| 1-3 | A dropdown custom field is created via `POST /projects/<id>/fields` and immediately appears via `GET /api/fields` | Pass |
| 4-6 | An issue created with a value for that field persists it and the value shows on the issue detail sidebar | Pass |
| 7-9 | Deleting the field definition removes its value from the issue (cascade) **and** the issue detail page still renders without error afterward | Pass |
| 10-13 | An automation rule with a condition (`new_status equals Testing`) does **not** fire a comment on an unrelated status change, but **does** fire - with `{issue_key}`/`{status}` placeholders correctly substituted - the moment the status actually becomes Testing | Pass |
| 14-16 | `assign_to_role` (developer) assigns a real developer id, drawn from more than one candidate across six separate issue creations - not a hardcoded id | Pass |
| 17-19 | The Edit Issue page loads and a submitted edit actually persists (title change confirmed in the store) | Pass |
| 20-22 | The board's `POST /board/move` drag-and-drop endpoint fires the identical `status_changed` automation the detail page's dropdown does - the same rule fires a second comment when moved into Testing via the board | Pass |
| 23-26 | An estimate is set, two time entries are logged, their sum is exactly 4.0 and the detail page displays that same total | Pass |
| 27-32 | A version is created, released (status flips), a second version is archived (status flips); the archived version disappears from `/versions`' main list while the still-active one remains; the archived version's name is still shown correctly on the issue it was already linked to | Pass |

All modified/added Python modules compile cleanly (`py_compile`, exit 0);
every touched template's Jinja `{% %}` block tags balance (checked
programmatically - `if`/`for`/`block` opens vs. `end*` closes, per file).

### Definition of Done

- [x] Deleting a custom field definition removes its values from every
      issue that had one, without erroring (confirmed via the FK's
      `ON DELETE CASCADE` and by reloading the issue detail page
      immediately afterward)
- [x] An automation rule with a condition does not fire on unrelated status
      changes, confirmed against the exact example the spec gives ("only
      when new status = Testing")
- [x] `assign_to_role` picks a real user with that role in the org, not a
      hardcoded id - confirmed by observing both configured developers get
      picked across repeated runs
- [x] Time spent total on the issue sidebar always equals the sum of its
      logged entries - confirmed by summing the entries directly and
      comparing to what the rendered page shows
- [x] Archiving a version hides it from the main Versions list but does not
      delete historical fix-version data on already-linked issues -
      confirmed the archived version's name still renders on the issue
      page after archiving

---

## 8. Interpretations and open items

**No automation rule "edit" route (§5.7)** - the single biggest judgment
call this stage rests on. The spec's routes table doesn't list one, but its
frontend prose mentions "edit" as a card action. Worth confirming whether a
real edit form was wanted; if so, it would reuse `automation_service.validate_rule`
and `update_rule` (both already written and unused by any route) almost
entirely as-is.

**`field_updated` is scoped to custom fields only (§5.3)** - a rule cannot
currently react to a standard field changing (e.g. priority escalating from
Medium to Critical). Flagged in case that was part of the intended scope;
extending it would mean adding diff-tracking to `issue_service.update_issue()`
for whichever standard fields matter.

**Condition fields are free text (§5.8)** - a typo in a condition's field
name fails silently (the rule just never fires) rather than erroring at
creation time. This favors "never crash" over "catch mistakes early"; a
future stage could validate known field names per trigger if that tradeoff
should flip.

**No custom-field reorder UI** - `display_order` is assigned once at
creation (append-only) and never rearranged from the UI, since the spec's
frontend section doesn't describe a control for it.

**The DDL has not been run against a live MySQL.** `scripts/create_tables.py`
was syntax-checked (`py_compile`) and reasoned through, but as in every
prior stage, the sandbox has no MySQL server to execute it against - in
particular, the `versions`/`custom_field_definitions` → `bugs` foreign key
ordering (both must be created before `bugs` on a fresh database), the
three new columns + FK on an *existing* `bugs` table via
`_ensure_bugs_stage9_columns()` and the `custom_field_values` cascade
delete have not been confirmed against a real server. Please run
`python -m scripts.create_tables` and check its output - it should print a
line for each of the five new tables, plus a line confirming
`bugs.time_estimate`/`time_remaining`/`fix_version_id` were added (only
relevant if your database predates this stage).

---

## 9. Notes for Stage 10

- `services/automation_service.execute_automation_rules()` is the one
  integration point every issue-mutating route already calls - if Stage 10
  adds any new way an issue can change (bulk operations, imports, etc.),
  wire it through this same function rather than duplicating trigger logic.
- `services/time_tracking_service.total_spent()` is the canonical "sum of
  entries" computation - reuse directly if Stage 10's reporting needs
  per-issue or per-project time totals, rather than re-summing
  `time_entries` elsewhere.
- `services/version_service.issue_counts()` (wrapping
  `issue_repository.count_by_fix_version`) already computes open/resolved/
  total per version - likely reusable as-is for any release-based reporting
  view.
- `custom_field_service.list_values_for_issue()`'s LEFT JOIN pattern (fields
  without a stored value still appear, blank) is the template to follow if
  a future stage ever needs "every X for issue Y, including X's that were
  never set."
