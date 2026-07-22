# Stage 7 - Kanban Board

## Goal
Give the team a visual, drag-and-drop board view of active work.

## Prerequisites
Stage 6 (status workflow) must be complete.

## Features to build
- Board shows four columns: **To Do, In Progress, Testing, Done** ("Idea" issues are intentionally excluded from the board - they live in the backlog, built in Stage 8).
- Filter the board by project and (once Stage 8 exists) by sprint.
- Click an avatar to quick-filter the board to just that assignee's cards.
- Group cards by assignee, priority, or issue type (a toggle/dropdown, not all at once).
- Drag a card to a different column to change its status - but only if the current user is allowed to (same `can_update_status` rule as Stage 6); dragging by someone unauthorized should visually snap back and show an error.
- Pagination or a "load more" control if a column has a large number of cards.

## Frontend - Design & Layout

> **Clone this exactly from `reference-ui/templates/board.html`.** Copy structure, classes, and wording as-is - adapt only route/variable names. The drag-and-drop behavior is already implemented in `reference-ui/static/js/script.js` (cloned in Stage 2) - reuse it, don't rewrite it from scratch.

**Board page** (`/board`):
- Top bar: Project selector dropdown, Sprint selector dropdown (Stage 8), Group-by dropdown, row of assignee avatars (click to filter, click again to clear).
- Four equal-width columns below, each with a header showing the column name and a card count.
- Each **card**: issue key (small, muted), issue-type icon, title (truncated with ellipsis if long), priority badge (colored dot or small flag icon), assignee avatar (bottom-right corner), story points (small badge, bottom-left), labels as small colored dots if present.
- Dragging: card lifts with a shadow while dragging; the target column highlights while hovering over it; releasing on an invalid target (unauthorized) animates the card back to its original spot with a brief error toast.
- Empty column state: light placeholder text like "No issues" rather than a blank space.

## Backend - Data Model & API

No new tables - this stage is purely a new way of querying and displaying `bugs` data already modeled in Stage 5/6.

**Routes:**
| Method | Path | Purpose |
|---|---|---|
| GET | `/board` | Render the board (accepts `project`, `sprint`, `group_by` query params) |
| POST | `/board/move` (or reuse `/issues/<id>/status`) | Update an issue's status from a drag action, returns JSON for AJAX |

**Query design note:** fetch all board-relevant issues for the selected project/sprint in one query (grouped by status in application code), rather than four separate queries per column - simpler and avoids column-count mismatches under concurrent updates.

## Definition of Done
- [ ] Board only shows To Do / In Progress / Testing / Done columns - never Idea.
- [ ] Dragging a card as an authorized user persists the new status after a page refresh.
- [ ] Dragging a card as an unauthorized user does not change the database, and the UI reflects that (card returns to original column).
- [ ] Switching projects reloads the board with only that project's issues.
- [ ] Clicking an assignee avatar filters the board to only their cards; clicking it again clears the filter.
