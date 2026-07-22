# Feature Verification Checklist - All 10 Stages, All Roles

Use this after Stage 10 is built to verify nothing was missed. It breaks
every feature down to the minute behaviors that are easy to skip, and
tags who should be tested against each one: **A**dmin, **P**roject
Manager, **D**eveloper, **T**ester.

Go stage by stage. For each item, actually log in as that role (not just
"Admin can probably do this too") and confirm the behavior - a lot of
these bugs only show up when tested as the *restricted* role, not the
powerful one.

---

## Stage 1 - Foundation & Setup
- [ ] App boots with one command, no manual steps beyond install + `.env`.
- [ ] `/health/db` returns 503 (not a crash/stack trace) when MySQL is stopped.
- [ ] Restarting the dev server keeps the same session secret (existing logins don't get silently logged out).
- [ ] `APP_ENV=production` with a weak/missing `SECRET_KEY` refuses to boot.

## Stage 2 - Authentication
- [ ] **A/P/D/T** - Register succeeds with valid data; password is hashed in the DB, never plaintext.
- [ ] Register with mismatched confirm-password is rejected server-side even if JS validation is bypassed.
- [ ] Register with an email that already exists is rejected with a clear message.
- [ ] Login with correct credentials works for every role.
- [ ] Login with wrong password AND login with a non-existent email show the **same** generic error message.
- [ ] Logout only works via POST - a GET request to a logout URL (or browser back button after logout) does not log the user out or leak protected content.
- [ ] Visiting any protected page while logged out redirects to `/login`, not a 500 error.
- [ ] Session cookie has `HttpOnly` and `SameSite=Lax` (check via browser dev tools).

## Stage 3 - Multi-Tenancy & Roles
- [ ] Registering with a brand-new org name creates the org, makes the user Admin, and auto-creates a default project.
- [ ] Registering with an existing org name creates a **pending** request, not an active login.
- [ ] A pending user sees only a "pending approval" message - no sidebar, no data, no API access via direct URL either.
- [ ] **A** - can see the Users admin page; **P/D/T** - cannot (both hidden in UI and blocked if the URL is visited directly).
- [ ] **A** - can approve a pending request; the new user can then log in immediately after.
- [ ] **A** - can reject a pending request; that person cannot log in afterward.
- [ ] **A** - can change another user's role, and it takes effect on that user's very next request (not just next login).
- [ ] Org A's Admin cannot see, approve, or reject Org B's pending requests, even by guessing a request ID in the URL.
- [ ] Requester IP is shown next to each pending registration request.

## Stage 4 - Projects & Issue Keys
- [ ] **A/P** - can create a project with name + key; **D/T** - cannot (UI hides the button AND the route rejects it directly).
- [ ] Duplicate project key within the same org is rejected.
- [ ] Same project key in two different orgs is allowed (no cross-org conflict).
- [ ] Projects list only shows the current org's projects, never another org's.
- [ ] Every new organization has exactly one project ("General") immediately, with no manual step required.

## Stage 5 - Core Issue CRUD & Hierarchy
- [ ] **A/P/D/T** - every role can create an issue (per the permission table, all four roles can create).
- [ ] Issue key auto-increments correctly per project (`WEB-1`, `WEB-2`, ...) even when created back-to-back quickly.
- [ ] Epic → can have Story/Task children. Story → can have Subtask children. Task/Bug/Subtask → cannot have children. All rejected combinations return a clear error, not a raw DB error.
- [ ] Setting a parent that would create a cycle (A→B→A) is rejected.
- [ ] Setting a parent from a **different project** is rejected.
- [ ] Screenshot upload: valid image works; disguised non-image (e.g. `.exe` renamed to `.png`) is rejected by content inspection, not just extension.
- [ ] Screenshot over the size limit is rejected with a clear message, not a crash.
- [ ] **D/T** - can edit an issue they reported; cannot edit someone else's issue.
- [ ] **A/P** - can edit any issue regardless of reporter.
- [ ] Guessing another organization's issue ID in the URL returns 404, not the issue's data.
- [ ] Labels, story points, due date, category, fix version (once Stage 9 exists) all save and display correctly.

## Stage 6 - Workflow & Status
- [ ] **T** - cannot change status of any issue (not assigned to Testers by design).
- [ ] **D** - cannot change status of an issue **not** assigned to them.
- [ ] **D** - **can** change status of an issue assigned to them, through all five statuses.
- [ ] **A/P** - can change status of any issue regardless of assignment.
- [ ] Assigning an issue in "To Do" auto-moves it to "In Progress"; assigning an issue already past "To Do" does **not** revert or skip its status.
- [ ] **A/P** - can assign/reassign; **D/T** - cannot assign issues to others.
- [ ] Every comment shows correct author, avatar/name, and timestamp, newest first.
- [ ] Watch toggle persists (watching, then reloading the page, still shows "watching").
- [ ] History panel shows status changes, assignment changes, and edits in correct chronological order - nothing silently missing.

## Stage 7 - Kanban Board
- [ ] Board shows only To Do / In Progress / Testing / Done - "Idea" issues never appear on the board.
- [ ] **D** - dragging a card assigned to them to a valid next column works and persists after refresh.
- [ ] **D** - dragging a card **not** assigned to them snaps back, no DB change.
- [ ] **T** - cannot drag any card to change status.
- [ ] Assignee avatar click filters the board correctly; clicking again clears the filter.
- [ ] Group-by (assignee / priority / type) regroups the same cards correctly under each mode.
- [ ] Switching project or sprint filter reloads the board with the correct scoped issues only.

## Stage 8 - Agile Planning
- [ ] **A/P** - can create a sprint, add a goal/dates; **D/T** - cannot manage sprints (per permission table).
- [ ] Only one sprint per project can be `active` at a time - starting a second one while one is active is rejected.
- [ ] Burndown chart's actual-progress line reflects real data, updates as issues move to Done, not a static/fake line.
- [ ] Closing a sprint updates its status and it no longer shows as the active sprint on the board.
- [ ] Issue linking: create a `blocks` link from A to B - A shows "Blocks B", B shows "Blocked by A" (correct direction on both sides from one link record).
- [ ] `relates_to` links show symmetrically on both sides.
- [ ] Unlinking from either issue's page removes the relationship from both.
- [ ] Saved filter reproduces the exact same result set later, including after new matching issues are added.
- [ ] Saved filters only show up for the user who saved them (unless `is_shared` is explicitly used).

## Stage 9 - Extensibility
- [ ] **A/P** - can create/delete custom fields per project; **D/T** - cannot manage field definitions.
- [ ] Custom field only appears on the Add/Edit form for **its own project**, not other projects in the same org.
- [ ] Dropdown field enforces at least 2 options at creation time.
- [ ] Required custom field blocks issue submission if left empty.
- [ ] Deleting a custom field definition removes its stored values from every issue, without breaking that issue's page.
- [ ] Automation rule with a trigger + condition fires **only** when the condition truly matches (test both a matching and a non-matching case).
- [ ] `assign_to_role` picks an actual user with that role in the org - test with more than one candidate to confirm it's not hardcoded to "first user found."
- [ ] Disabling a rule stops it from firing without deleting it; re-enabling restores it.
- [ ] Time entries: logging hours updates the "Time Spent" total on the sidebar to the exact sum.
- [ ] Original estimate and remaining estimate save and display independently of time spent.
- [ ] Version: create, assign as Fix Version on an issue, confirm issue counts (open/resolved/total) update correctly, release it, archive it (archived versions disappear from the main list but existing issue references remain intact).

## Stage 10 - Reporting, Dashboards & Ops
- [ ] **A/P** - can view Reports; **D/T** - cannot (hidden in UI and blocked on direct URL access).
- [ ] Report filters (date range, status, priority, project) actually narrow the chart data, not just the table.
- [ ] CSV export: a title/field starting with `=`, `+`, `-`, `@`, or a tab character is neutralized in the export (does not execute as a formula when opened in Excel/Sheets).
- [ ] Print view hides sidebar/header/filter controls, shows only the report content.
- [ ] New user's dashboard has a default widget layout with zero manual setup.
- [ ] Adding a widget, then removing a different one, preserves the rest of the layout and positions.
- [ ] Each of the 6 widget types (Statistics Summary, Recent Issues, Issues by Status/Priority/Severity/Type) renders real data, not placeholder/mock numbers.
- [ ] Assignment and status-change events actually queue a row in the email outbox; the background worker marks it sent (or failed, with a reason) rather than leaving it pending forever.
- [ ] Registration approval/rejection also queues a notification email.
- [ ] Disabling the notification worker via config does not break issue creation, assignment, or status changes elsewhere in the app.
- [ ] Repeated failed logins from the same identifier eventually get rate-limited, and the limit resets after the configured window.
- [ ] App runs correctly under the production WSGI entry point, not just the Flask dev server.

---

## Cross-cutting checks (test once, but they touch every stage)
- [ ] **Every** list/detail page filters by `organization_id` - spin up a second organization with its own data and confirm zero leakage in any page: issues, projects, sprints, versions, custom fields, automation rules, dashboards, saved filters.
- [ ] **Every** POST form includes and validates a CSRF token - submitting without one is rejected.
- [ ] Role checks are enforced **server-side** on every restricted route, not just hidden via UI (test by hitting the URL/endpoint directly as a lower-privileged role, e.g. with browser dev tools or curl).
- [ ] No page throws a raw stack trace to the browser on invalid input - everything fails with a clean flash message or JSON error.

---

Work through this list, check off what passes, and flag anything that
fails with the exact steps to reproduce it - that turns this from a
checklist into a bug list the next Claude session (or you) can fix
directly.
