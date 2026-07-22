# Stage 5 — Core Issue CRUD & Hierarchy

## Goal
This is the heart of the app: creating, viewing, and editing issues, with a
Jira-style type hierarchy and screenshot attachments.

## Prerequisites
Stage 4 (projects with issue keys) must be complete.

## Features to build
- Issue types: **Epic, Story, Task, Bug, Subtask**.
- Hierarchy rule: an Epic can contain Stories and Tasks. A Story can contain Subtasks. Task and Bug are flat (no children allowed to be attached to them... except Bug/Task themselves can't be parents). Reject any parent/child combination that breaks this, and reject a parent pointing to itself or to one of its own descendants (a cycle).
- Create issue: title, description, reproduction steps (optional, mainly for Bugs), category, priority, severity, project, issue type, optional parent, optional screenshot, labels, story points, due date.
- View issue detail: all fields, plus reporter and (once Stage 6 exists) assignment info.
- Edit issue: reporter, Admin, or Project Manager can edit; a Developer/Tester can only edit issues they reported.
- Screenshot upload: validate both file extension AND actual file content (open the image and check its real format) so someone can't upload a disguised executable with a `.png` extension. Limit file size. Store outside of anything web-servable directly with a random filename, not the original filename.
- Every issue gets an auto-generated key like `WEB-1`, `WEB-2` using the project's counter from Stage 4.

## Frontend — Design & Layout

> **Clone these exactly from `reference-ui/`:** `templates/add_bug.html`, `templates/edit_bug.html`, `templates/bug_details.html`, `templates/macros.html` (issue-type icon SVGs), `templates/view_bugs.html`. Copy structure, classes, and wording as-is — adapt only route/variable names. `bug_details.html` and `view_bugs.html` are large files that later stages (6, 8, 9) will extend further — clone the whole file now even though some of its sections (comments, history, linking, custom fields, time tracking) won't be wired up until those later stages.

**Add Issue page** (`/issues/add`):
- Two-column form layout: main column has Title, Description, Reproduction Steps (large textareas); side column has Project, Issue Type (icon-labeled dropdown — each type gets a distinct small icon/color, e.g. Epic=purple, Story=green, Task=blue, Bug=red, Subtask=gray), Priority, Severity, Category, Parent (dropdown filtered to valid parent types only, loaded based on chosen project), Labels (comma input), Story Points (number), Due Date, Screenshot (file picker with a preview thumbnail after selection).
- Submit button "Create Issue"; on success, redirect straight to the new issue's detail page.

**Issue Detail page** (`/issues/<id>`):
- Header: issue key + title, issue-type icon, priority/severity badges.
- Left/main column: full description, reproduction steps, screenshot (if present), and (later stages add) comments/history/time-tracking here too.
- Right sidebar: metadata panel — Reporter, Category, Labels (as small pill tags), Story Points, Due Date, Parent issue link (if any), list of child issues (if any).
- "Edit" button (visible only if the current user is allowed to edit this issue).

**Edit Issue page:** same layout as Add, pre-filled, plus the ability to replace or remove the existing screenshot.

## Backend — Data Model & API

**Table: `bugs`** (this is the single "issue" table — every issue type lives here, not in separate tables)
| Column | Type | Notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | |
| organization_id | INT | FK, NOT NULL |
| project_id | INT | FK, NOT NULL |
| issue_key | VARCHAR(30) | NOT NULL, unique per org |
| issue_type | ENUM('Epic','Story','Task','Bug','Subtask') | NOT NULL |
| parent_id | INT | FK → bugs.id, nullable |
| title | VARCHAR(255) | NOT NULL |
| description | TEXT | NOT NULL |
| reproduction_steps | TEXT | nullable |
| category | VARCHAR(80) | DEFAULT 'General' |
| priority | ENUM(...) | e.g. Low/Medium/High/Critical |
| severity | ENUM(...) | e.g. Minor/Major/Critical/Blocker |
| status | VARCHAR(50) | NOT ENUM — keep flexible for Stage 6, default 'Idea' or 'To Do' |
| reporter_id | INT | FK → users, NOT NULL |
| assigned_to | INT | FK → users, nullable (used from Stage 6) |
| screenshot_path | VARCHAR(255) | nullable, stores generated filename only |
| labels | VARCHAR(255) | comma-separated, nullable |
| story_points | INT | nullable |
| due_date | DATE | nullable |
| created_at / updated_at | DATETIME | |

**Routes:**
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/issues/add` | Show form / create issue |
| GET | `/issues/<id>` | Issue detail |
| GET/POST | `/issues/<id>/edit` | Show form / update issue |

**Hierarchy validation logic (implement as a reusable function, not inline in the route):**
- `Epic` → children may be `Story`, `Task`.
- `Story` → children may be `Subtask`.
- `Task`, `Bug`, `Subtask` → no children allowed.
- Reject a parent from a different project.
- Reject setting a parent that would create a cycle (walk up the chosen parent's ancestors; if the current issue appears, reject).

## Definition of Done
- [ ] Creating an issue with an invalid type/parent combination is rejected with a clear message, both via direct form submission and via a crafted request bypassing the UI.
- [ ] Issue keys are sequential and gap-free per project even when multiple issues are created in quick succession (test with concurrent requests if possible).
- [ ] Uploading a renamed non-image file as a "screenshot" is rejected.
- [ ] A Developer can edit their own reported issue but not someone else's (unless they're also Admin/PM).
- [ ] Viewing another organization's issue by guessing its ID returns 404, not the issue.
