# Stage 4 — Projects & Issue Keys

## Goal
Let an organization split its work into separate projects, each with a
short code, so issues can be identified like `WEB-1`, `API-42`.

## Prerequisites
Stage 3 (organizations, roles) must be complete.

## Features to build
- Admins and Project Managers can create a project: name + short key (2–6 uppercase letters, e.g. `WEB`).
- Every project belongs to exactly one organization.
- Each project auto-numbers its own issues starting at 1 (this counter is used starting in Stage 5).
- A projects list page showing every project in the org.
- When a new organization is created (Stage 3), auto-create a default "General" project so there's always at least one project to work in.

## Frontend — Design & Layout

**Projects page** (`/projects`):
- Grid or list of project cards: project name, key (shown as a colored badge/chip), short description.
- "+ New Project" button (visible only to Admin/PM), opens a small modal or inline form: Name, Key, Description.
- Clicking a project card leads toward its board (Stage 7) — for now it can just show a placeholder detail page.

## Backend — Data Model & API

**Table: `projects`**
| Column | Type | Notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | |
| organization_id | INT | FK → organizations, NOT NULL |
| name | VARCHAR(150) | NOT NULL |
| project_key | VARCHAR(10) | NOT NULL, uppercase |
| description | TEXT | nullable |
| next_issue_number | INT | NOT NULL DEFAULT 1 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

Add a unique constraint on `(organization_id, project_key)` — two projects in the same org can't share a key, but two different orgs can both have a `WEB` project.

**Routes:**
| Method | Path | Purpose |
|---|---|---|
| GET | `/projects` | List all projects in the user's org |
| POST | `/projects/create` | Create a project (Admin/PM only) |

**Key business rule to implement carefully:** issue-number allocation (used starting Stage 5) must be safe under concurrent creates — when an issue is inserted, read and increment `next_issue_number` inside the same transaction using a row lock (`SELECT ... FOR UPDATE`), so two people creating issues at the same moment never get the same number.

## Definition of Done
- [ ] Creating a project with a duplicate key (within the same org) is rejected with a clear error.
- [ ] Two different organizations can each have a project with the key `WEB` without conflict.
- [ ] A Developer/Tester cannot see a "New Project" button (role enforced both in the UI and on the server).
- [ ] A brand-new organization has exactly one project ("General") immediately after registration.
