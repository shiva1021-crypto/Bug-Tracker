# Stage 8 - Agile Planning

## Goal
Add Scrum-style planning: a backlog, sprints with a burndown chart, plus
issue linking and saved filters to help people find and relate work.

## Prerequisites
Stage 7 (board) must be complete.

## Features to build
**Sprints & Backlog**
- Backlog page: list of unassigned-to-sprint issues for a project, plus a way to create a sprint and drag/assign issues into it.
- A sprint has a name, optional goal, start date, end date, and one of three states: `future`, `active`, `closed`.
- Only one sprint per project can be `active` at a time.
- Starting a sprint moves it from `future` to `active`. Closing it moves it to `closed`.
- A burndown chart auto-renders for the currently active sprint: ideal-progress line vs. actual remaining work, day by day across the sprint's date range.

**Issue Linking**
- Link any two issues with a typed, directional relationship: `blocks` / `blocked by`, `relates to` (symmetric), `duplicates` / `duplicated by`, `clones` / `cloned by`.
- Show links on both linked issues' detail pages, with the correct direction label on each side.
- Unlink from either issue's detail page.

**Saved Filters**
- On the issue list/search page, let a user save their current filter combination (status, priority, project, assignee, etc.) under a name.
- Saved filters appear as clickable shortcut chips above the results table; clicking one re-applies that exact filter set.

## Frontend - Design & Layout

> **Clone `reference-ui/templates/backlog.html` exactly** for the sprint/backlog page. For the linked-issues panel and saved-filter chips, reference the corresponding sections already present in `reference-ui/templates/bug_details.html` and `reference-ui/templates/view_bugs.html` (both cloned whole in Stage 5) - wire up the logic, don't redesign the markup.

**Backlog page** (`/backlog`):
- Project selector at top.
- "Backlog" section: flat list of unsprinted issues, each row with a dropdown to assign it into an existing sprint (or "+ New Sprint").
- One collapsible section per sprint (future/active), each showing its issues, a story-point total, and Start/Close buttons as appropriate for its state.
- Active sprint section additionally shows the burndown chart inline (line chart, x-axis = sprint days, y-axis = remaining story points/issues).

**Issue Detail page (extend):** add a "Linked Issues" panel in the sidebar - list of "Blocks WEB-12", "Relates to API-4", etc., each clickable, plus a small form to add a new link (pick link type + target issue by key/search).

**Issue List page (extend):** row of saved-filter chips above the filter form; a "Save current filter" button next to the filter controls that prompts for a name.

## Backend - Data Model & API

**Table: `sprints`**
| Column | Type | Notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | |
| organization_id | INT | FK |
| project_id | INT | FK |
| name | VARCHAR(120) | |
| goal | TEXT | nullable |
| start_date / end_date | DATE | nullable |
| status | ENUM('future','active','closed') | DEFAULT 'future' |

**Alter `bugs`:** add `sprint_id INT NULL` (FK → sprints).

**Table: `issue_links`**
| Column | Type | Notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | |
| bug_id_a | INT | FK → bugs |
| bug_id_b | INT | FK → bugs |
| link_type | ENUM('blocks','relates_to','duplicates','clones') | |

Store the link once (A→B with a type); derive the reverse label for display on B's page (e.g. `blocks` on A shows as `blocked by` on B) rather than storing two rows.

**Table: `saved_filters`**
| Column | Type | Notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | |
| user_id | INT | FK |
| organization_id | INT | FK |
| name | VARCHAR(120) | |
| filter_data | JSON | the full query-param state |
| is_shared | TINYINT(1) | DEFAULT 0 (future: share with team) |

**Routes:**
| Method | Path | Purpose |
|---|---|---|
| GET | `/backlog` | Backlog + sprints view |
| POST | `/sprints/create` | Create a sprint |
| POST | `/sprints/<id>/start` | Start (only if no other active sprint in the project) |
| POST | `/sprints/<id>/close` | Close |
| POST | `/issues/<id>/sprint` | Assign an issue to a sprint |
| POST | `/issues/<id>/link` | Create a link |
| POST | `/issues/<id>/link/<link_id>/remove` | Remove a link |
| POST | `/filters/save` | Save current filter set |
| GET | `/filters` | List saved filters (used to render the chips) |

## Definition of Done
- [ ] Attempting to start a second sprint while one is already active in the same project is rejected.
- [ ] Burndown chart's "actual" line reflects real remaining story points/issues as of each day, not a static mock.
- [ ] A link created from Issue A to Issue B shows correctly worded on both issues without needing two link records.
- [ ] A saved filter reproduces the exact same result set when clicked later, including after new issues have been added.
