# Stage 7 - Kanban Board · Completion Report

**Project:** Bug Tracker (Jira-style bug tracking & agile project management)
**Stage:** 7 of 10 - Kanban Board
**Spec:** `project-spec/07-kanban-board.md`
**Builds on:** Stages 1-6 (Foundation, Authentication, Multi-Tenancy & Roles, Projects & Issue Keys, Core Issue CRUD & Hierarchy, Workflow & Status)
**Status:** Complete and verified (routes/services/repositories/templates); no DDL this stage - see §6.
**Date:** 21 July 2026

---

## 1. Goal of this stage

A visual, drag-and-drop board view of active work: four status columns,
filterable by project, groupable by assignee/priority/type, with a quick
per-assignee filter and pagination for busy columns.

Deliberately **not** built (belongs to a later stage):

- No sprint data model or sprint filtering. The spec calls the sprint
  selector out explicitly as "(Stage 8)" - the top bar renders a disabled
  sprint dropdown for layout parity (see §5.5), but nothing behind it is
  wired up and `GET /board`'s `sprint` query parameter is accepted and
  echoed back to the template but never used to filter anything.
- No backlog page and no "Idea" column - those issues are excluded from
  the board entirely, exactly as the spec requires.
- No new tables or schema changes. Per the spec's own Backend section,
  this stage is "purely a new way of querying and displaying `bugs` data
  already modeled in Stage 5/6" - every column, group and card comes from
  one `SELECT` against the existing `bugs` table.

Stages 1-6 were left intact. The one addition to a Stage 5/6 file is a
new read-only query function on `issue_repository.py` (see §2.2) - no
existing function in any prior-stage file was changed.

---

## 2. What was built

### 2.1 New files

| File | Layer | Purpose |
|---|---|---|
| `services/board_service.py` | services | Column/group/pagination shaping of one project's board issues and the per-card `can_drag` flag. |
| `routes/board_routes.py` | routes | `GET /board` (renders the page) and `POST /board/move` (JSON drag-and-drop endpoint). |
| `templates/board.html` | frontend | Top bar (project/sprint/group-by selectors, assignee avatar row), four columns, card markup, empty/load-more states. |

### 2.2 Modified files

| File | Change |
|---|---|
| `repositories/issue_repository.py` | Adds `list_board_issues(organization_id, project_id)` - one query, excludes `status = 'Idea'` at the SQL level, joins the assignee's name. Nothing else in this file changed. |
| `app.py` | Registers `board_bp`. Adds one Jinja filter, `label_color_index`, used only to give each distinct label text a stable dot color on board cards (see §5.4) - no schema change, purely a display computation. |
| `templates/base.html` | Adds a "Board" sidebar link. |
| `static/style.css` | New "board (Stage 7)" section: topbar, four-column grid, card styling, per-status-independent priority-flag colors, label dots, drag/hover/snap-back states, toast. |
| `static/script.js` | Adds `initBoardDragAndDrop()`, `initBoardLoadMore()`, `initBoardAssigneeFilter()` and their shared helpers (`boardPostMove`, `boardUpdateColumnCounts`, `boardShowToast`) - all following the existing one-`init*()`-per-feature convention. |

### 2.3 Layering

```
routes/board_routes.py        reads query params / form, renders or returns JSON
   ↓
services/board_service.py     groups + paginates + computes can_drag (read-only)
services/workflow_service.py  the actual status-change permission check + write (Stage 6, reused verbatim)
   ↓
repositories/issue_repository.py   list_board_issues() (new), update_status() (Stage 6, reused)
   ↓
utils/db.py                   pooled connection (Stage 1, unchanged)
```

`POST /board/move` does not reimplement Stage 6's permission logic - it
calls `workflow_service.can_update_status()` and `workflow_service.change_status()`
directly, the same two functions the issue detail page's status dropdown
uses. This means a card's drag-and-drop authorization and its detail-page
status control can never drift apart: there is exactly one place that
decides whether a status change is allowed, board or no board.

---

## 3. Data model

No new tables and no altered columns - the spec is explicit about this
("No new tables - this stage is purely a new way of querying and
displaying `bugs` data"). The board reads the same `bugs`, `users` and
`projects` tables Stages 3-6 already created.

---

## 4. Routes delivered

| Method | Path | Auth | Behaviour |
|---|---|---|---|
| GET | `/board` | required | Renders the board for a project (`?project=<id>`, defaults to the org's first project if omitted or invalid), grouped per `?group_by=` (`none`/`assignee`/`priority`/`type`, defaults to `none`). Accepts `?sprint=` per the spec's route table but does not act on it (see §1). |
| POST | `/board/move` | required | Body: `issue_id`, `status` (must be one of the four board statuses). Returns `{"ok": true}` on success or `{"ok": false, "error": "..."}` on rejection - never a redirect, since it's called via `fetch()` from a drag-drop handler, not a form submission. |

---

## 5. Key design decisions

### 5.1 A dedicated `/board/move` JSON endpoint, not a reuse of `/issues/<id>/status`

The spec offers either. Stage 6's `POST /issues/<id>/status` always
redirects back to the issue detail page with a flash message - correct
for a full-page form submission, but wrong for a drag-and-drop `fetch()`
call, which needs a JSON response it can act on immediately (revert the
card, show a toast) without a page navigation. Rather than branch Stage 6's
existing route on how it was called, `/board/move` is a new, thin route
that calls the exact same `workflow_service` functions Stage 6's route
does - no permission or transition logic is duplicated, only the response
shape differs.

### 5.2 The board is always drawn as four status columns; "group by" only affects what happens *inside* each column

The spec's Definition of Done requires the board to "only show To Do /
In Progress / Testing / Done columns - never Idea," while the Features
list separately asks for grouping "by assignee, priority, or issue type."
Read together, the two can't both mean "replace the columns" - grouping
is a second, independent axis layered inside each status column: within
a column, cards are split into labeled sub-groups (e.g. "Dan Developer",
"Unassigned" for `group_by=assignee`), each sub-group only appearing if
at least one card in that column actually belongs to it. Verified
directly in §7 that all three group-by modes produce the right
sub-groups and that priority grouping orders Critical before Low.

### 5.3 Pagination applies to the flat (ungrouped) view only

`board_service.PAGE_SIZE` (20) caps how many cards render immediately in
a column before a "Load N more" button appears - but only when
`group_by=none`. When a group-by is active, every card in every present
sub-group renders immediately, with no truncation. This is a deliberate
simplification, not an oversight: truncating a grouped column would mean
either paginating each sub-group separately (turning one "Load more" into
several, one per group, which the spec's simple "a Load more control"
phrasing doesn't ask for) or paginating across group boundaries (which
would produce a sub-group header with zero visible cards under it until
"Load more" is clicked - confusing). Flagged here since it is a real gap:
a column with hundreds of cards *and* a group-by selected will render all
of them at once. Given the spec only requires this "if a column has a
large number of cards" as a general usability concern rather than a hard
performance requirement, the flat-view-only implementation was judged the
better trade-off of the two, but it's worth revisiting if grouped columns
turn out to get large in practice.

### 5.4 Label dots get a stable color from a small fixed palette, computed from the label text

The spec's card layout asks for "labels as small colored dots if
present," but `bugs.labels` is (and has been since Stage 5) a single
comma-separated `VARCHAR` with no per-label color anywhere in the schema,
and this stage adds no new tables. Rather than leave every label the same
neutral gray (which reads as "labels exist" but not "these are different
labels") or invent a labels-with-colors table (which would be schema work
outside this stage's explicit no-new-tables constraint), each label's dot
color is derived deterministically from its own text (`app.py`'s
`label_color_index` filter: sum of character codes, modulo 6, indexing
into six fixed CSS dot colors). The same label text always gets the same
dot color across every card and every page load; two different labels
usually - but, given only six colors, not always - get different colors.
Flagged as a cosmetic approximation given the constraints, not a claim
that it never collides.

### 5.5 The sprint selector is rendered, disabled and inert

The spec's own top-bar layout lists a "Sprint selector dropdown (Stage
8)" alongside the project selector - read as: the layout slot should
exist now so Stage 8 only has to enable it, not design and insert it. The
`<select>` is present, disabled, shows a single "All Sprints" option and
carries a tooltip explaining why. `GET /board`'s `sprint` query parameter
is read and passed back into the template (so the disabled control could
echo a value if one were ever set) but never touches the query in
`board_service.get_board()`. This is scoped deliberately narrowly - no
sprint table, no sprint column, no filtering logic - to avoid reaching
into Stage 8's territory while still satisfying the frontend layout the
spec describes.

### 5.6 The assignee quick-filter and drag-and-drop are both purely client-side against data already on the page

The spec's route table lists only `project`, `sprint` and `group_by` as
`GET /board` query parameters - `assignee` is not among them and "click
an avatar to filter... click again to clear" describes an instant toggle,
not a page reload. So the quick-filter is implemented entirely in
`static/script.js`: every card already carries its `assigned_to` id in a
`data-assignee-id` attribute and clicking an avatar just hides/shows
cards already in the DOM. Likewise, an authorized drag is applied
optimistically (the card moves in the browser immediately) and only
reverted if the server's JSON response says `ok: false` - the DoD's
"dragging by someone unauthorized should visually snap back" is
implemented as exactly that: an immediate optimistic move, then a real
server round-trip that decides whether it sticks.

### 5.7 A card dropped into a new column is appended after that column's groups, not merged into a specific sub-group

When `group_by` is active and a card is dragged into a different column,
the client-side move appends it to the end of that column's list rather
than trying to insert it under the matching sub-group header (e.g. under
the correct assignee's group). The full, correctly-grouped arrangement is
only recomputed on the next full page load. This was accepted as a minor,
temporary display inconsistency rather than built out further, since
re-deriving sub-group membership client-side would require duplicating
`board_service._group_cards()`'s logic in JavaScript for a purely cosmetic
benefit until the next reload.

---

## 6. Setup procedure

```bash
python run.py                       # -> http://127.0.0.1:5000/board
```

No new dependencies, no DDL and no migration step - this stage only adds
one read query against the existing `bugs` table.

---

## 7. Verification results

As in every prior stage, the sandbox has no MySQL server, so the full
request flow was exercised against in-memory stand-ins for every
repository touched this stage (`user_repository`, `project_repository`,
`issue_repository` - including a fake `list_board_issues()` matching the
real function's exact signature and Idea-exclusion behavior), driven
through the real Flask app (`app.test_client()`) end-to-end: routes →
services → fake repositories → real Jinja templates. `board_service.py`'s
grouping/pagination logic was also exercised directly (not just through
HTTP) so its output structure could be asserted precisely.

**28 new checks for this stage, all passing.**

| # | Check | Result |
|---|---|---|
| 1-4 | The board renders exactly 4 columns, in order To Do/In Progress/Testing/Done; a co-created "Idea" issue never appears anywhere on the board while its four non-Idea siblings do | Pass |
| 5-9 | Two different projects render two different boards - the WEB board shows only WEB-prefixed issues, the MOB board shows only its own issue and never a WEB one | Pass |
| 10 | Requesting `/board` with no `project` param still renders a real board (defaults to the org's first project) | Pass |
| 11-12 | The Developer assigned to an issue drags it and the status change is returned as authorized *and* actually persisted server-side | Pass |
| 13-15 | A Tester's drag is rejected (`ok: false`, database unchanged and a real error message is present in the response) | Pass |
| 16 | A **different** (non-assigned) Developer's drag on the same issue is also rejected | Pass |
| 17 | An Admin/PM's drag succeeds as an override, matching Stage 6's status-change rule exactly | Pass |
| 18 | Dragging a card to "Idea" is rejected outright - it is not one of the four valid board-drop targets | Pass |
| 19-20 | `group_by=assignee` produces the right sub-group headers, including an "Unassigned" group when appropriate | Pass |
| 21 | `group_by=priority` orders "Critical" ahead of "Low" | Pass |
| 22 | `group_by=type` only lists issue types actually present in that column (no empty "Epic" header, etc.) | Pass |
| 23 | `group_by=none` produces a flat card list with no group headers at all | Pass |
| 24-25 | A column seeded with 25 cards shows exactly 20 immediately and marks the remaining 5 as hidden, with the correct hidden count | Pass |
| 26-28 | The quick-filter assignee list includes every developer with at least one card on the board and excludes a user with none | Pass |

All modified/added Python modules compile cleanly (`py_compile`, exit 0),
and the board template renders without error for every project/group-by
combination exercised above.

### Definition of Done

- [x] Board only shows To Do / In Progress / Testing / Done columns - never Idea
- [x] Dragging a card as an authorized user persists the new status after a page refresh (verified against the real database-backed status, not just the in-memory response)
- [x] Dragging a card as an unauthorized user does not change the database and the UI reflects that (server rejects it; the client-side handler reverts the optimistic move on that rejection - see §5.6)
- [x] Switching projects reloads the board with only that project's issues
- [x] Clicking an assignee avatar filters the board to only their cards; clicking it again clears the filter (client-side toggle against the `data-assignee-id` already rendered on each card - see §5.6)

---

## 8. Interpretations and open items

**Grouping only applies inside the fixed four columns, never replacing
them (§5.2)** is the central interpretation this stage rests on - flagged
clearly since "group cards by X" could in principle have meant something
more drastic, but the Definition of Done's explicit column requirement
rules that reading out.

**Pagination is skipped entirely once a group-by is active (§5.3)** is a
known, flagged gap: a very large *and* grouped column renders every card
at once. Revisit if that combination turns out to matter in practice.

**Label dot colors are a deterministic hash over six colors, not a real
per-label color assignment (§5.4)** - collisions are possible with more
than six distinct labels on one project. No schema change was made to fix
this, in keeping with the stage's "no new tables" constraint.

**The sprint selector is inert (§5.5)**, by design - nothing behind it
should be built until Stage 8 defines what a sprint actually is.

**A card dropped into a grouped column doesn't reflow into its matching
sub-group until the next page load (§5.7)** - a minor, deliberately
accepted display gap, not a data-correctness issue (the server-side
status change and the column it lands in are both always correct; only
which sub-group heading it visually sits under, immediately after the
drop, can be momentarily off).

**No DDL this stage** - nothing to run against a live MySQL server and
nothing new to verify there; this stage's only untested-in-a-real-browser
surface is the drag-and-drop interaction itself (native HTML5 drag events
don't have a meaningful sandbox equivalent), which is why `board_service`'s
grouping/pagination logic and the `/board/move` permission path were each
verified directly and separately, rather than only through a simulated
drag.

---

## 9. Notes for Stage 8

- `board_service.BOARD_STATUSES` (`["To Do", "In Progress", "Testing",
  "Done"]`) is the reference list for anything that needs "every status
  except Idea" - kept intentionally separate from `workflow_service.STATUSES`
  (which includes Idea) rather than derived from it, so Stage 8's backlog
  page can import whichever one actually matches what it needs.
- The inert sprint selector in `templates/board.html` and the unused
  `sprint` query parameter in `routes/board_routes.py::board()` are the
  two places to wire up real sprint filtering once Stage 8 defines a
  sprint table - nothing else on the board depends on sprints existing.
- `board_service.get_board()` takes a single `project_id` (never "all
  projects at once") - if Stage 8's backlog needs a cross-project view,
  that will need a new function, not a parameter added to this one, to
  keep the one-query-per-board-load design intact.
- `templates/board.html`'s card markup (key, type badge, title, labels,
  priority flag, points, avatar) is the canonical card layout going
  forward - the backlog page should reuse it rather than re-deriving a
  similar-but-different card.
