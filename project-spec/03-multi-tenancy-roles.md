# Stage 3 - Multi-Tenancy & Roles

## Goal
Turn the single-user login system into a multi-organization system with
role-based permissions, so many separate companies/teams can use the same
app without ever seeing each other's data.

## Prerequisites
Stage 2 (working login/session) must be complete.

## Features to build
- Every user belongs to exactly one **organization**.
- Registering with a **new** organization name makes you that org's first user, automatically an **Admin**.
- Registering with an organization name that **already exists** creates a pending registration request that an admin of that org must approve or reject.
- Four roles: **Admin**, **Project Manager**, **Developer**, **Tester** - each with different permissions (defined below and enforced in every later stage).
- Admin panel: list all users in the org, change a user's role, approve/reject pending registration requests.
- Every database query from this point forward must filter by `organization_id` - this is the tenant isolation boundary and must never be skipped.

## Role permission matrix (enforce this everywhere going forward)
| Action | Admin | Project Manager | Developer | Tester |
|---|---|---|---|---|
| Create issues | ✓ | ✓ | ✓ | ✓ |
| Edit any issue | ✓ | ✓ | own reports only | own reports only |
| Assign issues | ✓ | ✓ | ✗ | ✗ |
| Update status of assigned issue | ✓ | ✓ | ✓ (if assigned to them) | ✗ |
| Manage sprints | ✓ | ✓ | ✗ | ✗ |
| Manage users | ✓ | ✗ | ✗ | ✗ |
| View reports | ✓ | ✓ | ✗ | ✗ |

## Frontend - Design & Layout

> **Clone this exactly from `reference-ui/templates/users.html`.** Copy structure, classes and wording as-is - adapt only route/variable names. The sidebar shown here is part of `base.html` (already cloned in Stage 2) - extend its nav links per role, don't rebuild the sidebar itself.

**Register page (update from Stage 2):** add an "Organization Name" field. Show helper text: "New name → you become the admin. Existing name → your request needs approval."

**Pending approval page:** if a user's registration is awaiting approval, show a simple "Your request is pending admin approval" message instead of the app, no sidebar.

**Admin → Users page** (`/admin/users`):
- Table of all users in the organization: Name, Email, Role, Joined date, with a role dropdown per row (admin can change any user's role inline).
- A separate section/tab: "Pending Registrations" - table of requests with Approve/Reject buttons and the requester's IP address shown for context.

**Sidebar (introduce now, used by every later stage):** collapsible left sidebar with navigation links. Which links appear depends on role - e.g. only Admin sees "Users"; only Admin/PM see "Reports" (added Stage 10).

## Backend - Data Model & API

**Table: `organizations`**
| Column | Type | Notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | |
| name | VARCHAR(150) | UNIQUE, NOT NULL |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

**Alter `users`:** add `organization_id INT NOT NULL` (FK → organizations, ON DELETE CASCADE), add `role ENUM('admin','project_manager','developer','tester') NOT NULL DEFAULT 'tester'`.

**Table: `registration_requests`**
| Column | Type | Notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | |
| organization_id | INT | FK → organizations |
| full_name | VARCHAR(150) | |
| email | VARCHAR(150) | |
| password_hash | VARCHAR(255) | |
| requested_role | ENUM(...) | same roles as users |
| requester_ip | VARCHAR(45) | |
| status | ENUM('pending','approved','rejected') | DEFAULT 'pending' |
| created_at | DATETIME | |

**Routes:**
| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/users` | List users + pending requests (Admin only) |
| POST | `/admin/users/<id>/role` | Change a user's role (Admin only) |
| POST | `/admin/requests/<id>/approve` | Approve a pending registration (Admin only) |
| POST | `/admin/requests/<id>/reject` | Reject a pending registration (Admin only) |

**Session data (update from Stage 2):** now also store `organization_id` and `role`. Re-check the role from the database on sensitive actions rather than trusting a stale session value indefinitely (someone's role may have just been downgraded by an admin).

## Definition of Done
- [ ] Registering a brand-new org name makes you Admin immediately, with a default project (see Stage 4) auto-created.
- [ ] Registering an existing org name creates a pending request, not an active account.
- [ ] A pending user cannot access any page except a "pending approval" notice.
- [ ] An Admin from Org A cannot see or approve requests from Org B.
- [ ] Every list/detail query added from this stage onward includes `WHERE organization_id = %s`.
- [ ] Changing a user's role takes effect on their next request (not just at their next login).
