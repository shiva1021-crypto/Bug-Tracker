# Stage 6 - Workflow & Status

## Goal
Give every issue a defined lifecycle, restrict who can move it and keep a
full audit trail of every change.

## Prerequisites
Stage 5 (issue CRUD) must be complete.

## Features to build
- Five statuses, in order: **Idea → To Do → In Progress → Testing → Done**.
- Only the assigned Developer can move an issue between statuses (Admin/PM can too, as an override). Testers and non-assigned Developers cannot change status directly.
- Assigning an issue to someone auto-transitions it from "To Do" to "In Progress" (if it was in "To Do").
- Every status change, assignment change and significant field edit is recorded in a history/audit table - who did it, when and what changed.
- Comments: threaded, newest-first, visible to anyone who can view the issue.
- Watchers: any user can "watch" an issue to be notified (notifications themselves arrive in Stage 10) of status changes.

## Frontend - Design & Layout

> **Reference `reference-ui/templates/bug_details.html`** - it already contains the status badge, assignment control, watch toggle, comments section and history panel markup in full (this file was cloned whole in Stage 5). Wire up the logic for these sections now; don't redesign what's already there.

**Issue Detail page (extend Stage 5's layout):**
- Status shown as a colored badge near the title (distinct color per status - suggest: Idea=gray, To Do=blue, In Progress=amber, Testing=purple, Done=green).
- If the current user is allowed to change status, show a dropdown or a row of buttons for the next valid status/statuses.
- Assignment control in the sidebar: avatar + name of assignee, with a dropdown to reassign (Admin/PM only) listing developers in the project's organization.
- Watch toggle: an eye icon button, filled when watching, outline when not, with a watcher count next to it.
- **Comments section** below the description: a text box to add a new comment and a list of existing comments below it, each showing commenter name, avatar, timestamp and text.
- **History panel** (can be a collapsible section or a tab): chronological list of "X changed status from Y to Z", "X assigned to Y", "X edited the issue", each with a timestamp.

## Backend - Data Model & API

**Alter `bugs`:** ensure `status VARCHAR(50)` (not an ENUM - keep it flexible for future custom workflows).

**Table: `comments`**
| Column | Type | Notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | |
| bug_id | INT | FK → bugs, NOT NULL |
| user_id | INT | FK → users, NOT NULL |
| comment | TEXT | NOT NULL |
| created_at | DATETIME | |

**Table: `bug_history`**
| Column | Type | Notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | |
| bug_id | INT | FK → bugs |
| changed_by | INT | FK → users |
| old_status | VARCHAR(50) | nullable |
| new_status | VARCHAR(50) | nullable |
| old_assigned_to | INT | nullable |
| new_assigned_to | INT | nullable |
| change_note | VARCHAR(255) | free-text summary, e.g. "Bug WEB-3 created" |
| changed_at | DATETIME | |

**Table: `issue_watchers`**
| Column | Type | Notes |
|---|---|---|
| bug_id | INT | FK → bugs |
| user_id | INT | FK → users |
| (bug_id, user_id) | | composite unique/primary key |

**Routes:**
| Method | Path | Purpose |
|---|---|---|
| POST | `/issues/<id>/status` | Change status (permission-checked) |
| POST | `/issues/<id>/assign` | Assign/reassign (Admin/PM only) |
| POST | `/issues/<id>/comment` | Add a comment |
| POST | `/issues/<id>/watch` | Toggle watching |

**Permission rule (`can_update_status`) to implement as a reusable check:** true if current user is Admin/PM, OR (current user is a Developer AND is the assigned user on this issue).

## Definition of Done
- [ ] A Tester cannot move an issue's status via the API even if they craft the request directly.
- [ ] Assigning an unassigned "To Do" issue moves it to "In Progress" automatically; assigning an issue already "In Progress" or beyond does not change its status.
- [ ] Every status change and assignment appears in the history panel in the correct order.
- [ ] Watching an issue and then someone else changing its status is recorded (actual email delivery comes in Stage 10 - for now, just confirm the watcher relationship is stored correctly).
