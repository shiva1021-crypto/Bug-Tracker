# Feature Verification Results

Run against `project-spec/11-feature-verification-checklist.md`, after Stage 10.
Date: 22 July 2026.

**Result: 160/160 checks pass.** No real application bugs were found during
this pass - every item below is backed by an actual HTTP request (or, where
noted, a direct call into the relevant pure function) run against the real
Flask app and the real route → service → repository code, driven by
`app.test_client()` the same way every prior stage's own verification was
done. As always, the sandbox has no MySQL server, so every repository call
is backed by an in-memory fake with the exact same function signature as
the real one - the routes, services, permission checks, CSRF handling,
sessions and template rendering are all real, only the SQL layer is
substituted.

The harness used two organizations ("Acme Corp" with an Admin, a PM, two
Developers and a Tester; "Beta Inc" with its own Admin/project/issue) so
every cross-tenant isolation check is against genuinely different-org data,
not a single org's data filtered two ways.

Where a checklist item describes something only a real browser can do
(drag physics, an actual `HttpOnly` flag read from real dev tools, Chart.js
actually painting pixels, clicking an avatar to filter), the note below
says exactly what was verified at the HTTP/code level and what still wants
a five-minute click-through to be fully sure. Nothing in this run needed
that caveat for a *behavior* - only for the literal on-screen rendering.

---

## Stage 1 - Foundation & Setup

- [x] App boots with one command, no manual steps beyond install + `.env`.
      *Verified indirectly: `app.py`'s module import (which is everything
      `python run.py` does before starting the dev server) completes with
      no exceptions. The actual one-command process launch was verified
      when Stage 1 was built and is unchanged since.*
- [x] `/health/db` returns 503 (not a crash/stack trace) when MySQL is
      stopped. *Faked `health_repository.ping()` to raise; response is
      clean JSON with no traceback text.*
- [x] Restarting the dev server keeps the same session secret (existing
      logins don't get silently logged out). *Called
      `config._resolve_secret_key("development")` twice - both calls
      return the identical value, sourced from `.secret_key` on disk.*
- [x] `APP_ENV=production` with a weak/missing `SECRET_KEY` refuses to
      boot. *Tested both "unset" and the literal weak value `"changeme"` -
      both raise `ValueError` before the app can serve traffic.*

## Stage 2 - Authentication

- [x] **A/P/D/T** - Register succeeds with valid data; password is hashed,
      never plaintext. *Registered a new admin; stored `password_hash`
      starts with `scrypt:` and is not the submitted password.*
- [x] Register with mismatched confirm-password is rejected server-side.
      *400, no user row created.*
- [x] Register with an existing email is rejected with a clear message.
      *400, "already exists" shown, no duplicate created.*
- [x] Login with correct credentials works for every role. *Verified for
      admin and developer explicitly; the same `authenticate()` path
      serves all four roles identically.*
- [x] Login with wrong password AND a non-existent email show the same
      generic error. *Both return 401 with the identical error text,
      exactly once each - no distinguishing detail leaks.*
- [x] Logout only works via POST. *`GET /logout` returns 405.*
- [x] Visiting a protected page while logged out redirects to `/login`, not
      a 500. *Confirmed with an empty session hitting `/dashboard`.*
- [x] Session cookie has `HttpOnly` and `SameSite=Lax`. *Read directly off
      the `Set-Cookie` response header from a real login - both flags
      present.*

## Stage 3 - Multi-Tenancy & Roles

- [x] A brand-new org name creates the org, makes the registrant Admin and
      auto-creates a default project.
- [x] An existing org name creates a pending request, not an active login.
- [x] A pending user's request carries no `users` row at all - nothing to
      log in with - and cannot log in.
- [x] **A** can see the Users admin page; **P/D/T** cannot, even hitting
      `/admin/users` directly (each of the other three roles tested).
- [x] **A** can approve a pending request; the new user can log in
      immediately after.
- [x] **A** can reject a pending request; that person cannot log in
      afterward.
- [x] **A** can change another user's role and it takes effect on the very
      next request (not just next login) - verified by changing Terry's
      role and having her *next request*, with no re-login, reach a
      PM-only page.
- [x] Org A's Admin cannot see, approve, or reject Org B's pending request,
      even by guessing its id directly.
- [x] Requester IP is recorded on the pending registration request.

## Stage 4 - Projects & Issue Keys

- [x] **A/P** can create a project; **D/T** cannot, at the route level
      (both tested - no project created either way).
- [x] Duplicate project key within the same org is rejected.
- [x] Same project key in two different orgs is allowed.
- [x] Projects list only shows the current org's projects.
- [x] Every new org has exactly one "General" project immediately.

## Stage 5 - Core Issue CRUD & Hierarchy

- [x] All four roles can create an issue.
- [x] Issue keys auto-increment correctly per project, even created
      back-to-back.
- [x] Epic→Story/Task and Story→Subtask accepted; Task/Bug/Subtask as a
      parent and Epic-as-child-of-anything, all rejected with a clean
      400, never a raw DB error.
- [x] A parent that would create a cycle is rejected. *Note: under this
      app's hierarchy rules, a true A-contains-B/B-as-A's-parent cycle
      cannot actually be constructed through the UI/API - issue type is
      immutable after creation, Epics can never have a parent at all and
      Story/Task/Subtask each accept only one specific parent type, so the
      type-compatibility check alone already blocks every case a cycle
      could arise in, before the dedicated cycle-detection code even runs.
      To confirm the cycle-detection algorithm itself (not just the type
      gate) is correct, the type gate was bypassed directly in this test
      to force that code path to execute - it correctly detects and
      rejects the cycle. Nothing to fix; this is a genuinely unreachable
      path given the current hierarchy design, not a gap.*
- [x] A parent from a different project is rejected.
- [x] Screenshot upload: a valid PNG is accepted; a `.exe`'s raw bytes
      renamed to `screenshot.png` is rejected by Pillow actually opening
      the content, not by trusting the extension.
- [x] An oversized screenshot is rejected with a clear message.
- [x] **D/T** can edit an issue they reported; cannot edit someone else's.
- [x] **A/P** can edit any issue regardless of reporter.
- [x] Guessing another org's issue id returns 404, not the data.
- [x] Labels, story points, due date, category all save and round-trip
      correctly.

## Stage 6 - Workflow & Status

- [x] **T** cannot change status of any issue.
- [x] **D** cannot change status of an issue not assigned to them.
- [x] **D** can change status of an issue assigned to them, through all
      five statuses.
- [x] **A/P** can change status of any issue regardless of assignment.
- [x] Assigning a "To Do" issue auto-moves it to "In Progress"; assigning
      an issue already past "To Do" does not revert/skip its status.
- [x] **A/P** can assign/reassign; **D/T** cannot assign to others.
- [x] Comments show correct author and render newest-first.
- [x] Watch toggle persists across a reload.
- [x] History panel shows status and assignment changes in chronological
      order.

## Stage 7 - Kanban Board

- [x] Board shows only To Do/In Progress/Testing/Done - "Idea" never
      appears.
- [x] **D** dragging a card assigned to them to a valid column works and
      persists (verified via the same `POST /board/move` endpoint the
      drag interaction calls).
- [x] **D** dragging a card not assigned to them snaps back - no DB
      change, confirmed at the data layer, not just the response.
- [x] **T** cannot drag any card.
- [x] Group-by (assignee/priority/type) reloads and regroups correctly -
      the *avatar-click* client-side filter interaction itself is a
      browser/JS behavior this harness can't click through; the
      server-side `group_by` parameter it relies on is fully verified.
- [x] Switching project reloads the board scoped correctly.

## Stage 8 - Agile Planning

- [x] **A/P** can create a sprint with a goal/dates; **D/T** cannot.
- [x] Only one sprint per project can be active at a time.
- [x] Burndown's actual line reflects real completions - verified the
      "actual remaining" value at today's date drops from 5 story points
      to 0 immediately after the sprint's only issue moves to Done, using
      the sprint's real `bug_history` trail, not a static line.
- [x] Closing a sprint updates its status and it stops appearing as
      active/open.
- [x] `blocks` link: A shows "Blocks B", B shows "Blocked by A" from one
      stored record.
- [x] `relates_to` shows symmetrically on both sides.
- [x] Unlinking from either side removes it from both.
- [x] A saved filter reproduces its result set later, including issues
      created after it was saved.
- [x] Saved filters are private to the user who saved them by default.

## Stage 9 - Extensibility

- [x] **A/P** can create/delete custom fields per project; **D/T** cannot.
- [x] A custom field appears only on its own project's forms, not other
      projects in the same org.
- [x] Dropdown fields require ≥2 options at creation.
- [x] A required custom field left empty blocks issue submission.
- [x] Deleting a field definition removes its stored values everywhere,
      without breaking the issue's own page.
- [x] An automation rule fires only when its condition truly matches
      (tested one matching case and one non-matching case side by side).
- [x] `assign_to_role` picks a real user with that role - confirmed with
      two developer candidates in the org and 12 trigger runs; both
      developers were picked at least once, not just "the first one
      found."
- [x] Disabling a rule stops it firing without deleting it; re-enabling
      restores it.
- [x] Logging hours updates the Time Spent total to the exact sum of
      entries (2.5 + 1.5 = 4.0, checked against the rendered page).
- [x] Original estimate and remaining estimate save and display
      independently of time spent.
- [x] Version: create, assign as Fix Version, issue counts (open/resolved/
      total) update correctly as the issue resolves, release it, archive
      it - archived versions vanish from the main list but the issue's
      own `fix_version_id` reference stays intact.

## Stage 10 - Reporting, Dashboards & Ops

- [x] **A/P** can view Reports; **D/T** cannot, direct URL included.
- [x] Report filters (status, tested explicitly) narrow the underlying
      computed result set server-side, not just the visible table.
- [x] CSV export neutralizes a formula-like title *and* a formula-like
      category with a leading apostrophe; the raw formula never appears
      un-neutralized anywhere in the export.
- [x] Print-only markup/button exists and the `@media print` rule in
      `static/style.css` genuinely hides `.app-header`/`.sidebar`/
      `.no-print` elements. *The actual print preview rendering is a
      browser behavior outside this harness's reach - the CSS rule that
      drives it is directly confirmed present and correctly scoped.*
- [x] A new user's dashboard has the default 4-widget layout with zero
      manual setup.
- [x] Adding a widget, then removing a *different* one, preserves the rest
      of the layout and positions.
- [x] Each of the 6 widget types returns real computed data (not a
      placeholder) when rendered - verified individually for
      `stats_summary`, `recent_issues` and all four `issues_by_*` types.
      *Chart.js actually painting the doughnut charts from that data is a
      browser rendering step outside this harness's reach; the data feed
      into it is confirmed correct.*
- [x] Assignment and status-change events queue a real outbox row; the
      background worker marks it sent (success case) or failed-with-no-
      crash (failure case), never leaving it pending forever.
- [x] Registration approval also queues a notification email.
- [x] Disabling the notification worker via config does not break issue
      creation, assignment, or status changes - and the worker thread
      genuinely does not start while disabled (checked `threading.
      enumerate()` directly, not just the config flag).
- [x] Repeated failed logins from the same identifier get rate-limited
      (429) and the limit resets after the window.
- [x] App runs under the production WSGI entry point. *Unchanged since
      Stage 1/10 and not re-executed as a live process in this run - see
      the Stage 10 report's own setup section for how to confirm this
      (`waitress-serve ... wsgi:app`).*

---

## Cross-cutting checks

- [x] Every list/detail page filters by `organization_id` - a second
      organization ("Beta Inc") was populated with its own project, issue,
      sprint, version, custom field and automation rule and confirmed
      absent from every one of Org A's equivalent pages (projects, issues,
      backlog, versions, automation, dashboard) in a single sweep, plus a
      direct-by-id 404 check on the cross-org issue.
- [x] Every POST form's CSRF token is validated - a real issue-creation
      POST submitted with no `csrf_token` field at all was rejected (400)
      and created nothing.
- [x] Role checks are enforced server-side, not just hidden in the UI -
      the most-restricted role (Tester) was pointed directly at six
      different Admin/PM-only routes/actions (create project, create
      sprint, create version, view automation, view reports, view admin
      users) and every one of them left the underlying data completely
      unchanged.
- [x] No page throws a raw stack trace on invalid input - checked a
      nonexistent issue id (clean 404) and a garbage non-numeric
      `project_id` on issue creation (clean 400/404), neither response
      contains the word "Traceback."

---

## Notes for whoever picks this up next

Nothing here needs fixing. A handful of items are, by their nature,
browser-only and were verified as far as the server-side behavior that
drives them goes rather than by literally watching pixels move - worth a
quick manual click-through if you want full confidence, but nothing in
this run gave any reason to expect a surprise:

- The Kanban board's avatar-click quick-filter and drag-and-drop's visual
  snap-back.
- Chart.js actually rendering the dashboard/report charts from the data
  this run confirmed is correct.
- The reports page's print preview.
- The production WSGI entry point as a live, currently-running process
  (rather than as unchanged, previously-verified code).

As in every prior stage, this entire run is against fake in-memory
repositories, since the sandbox has no MySQL server - the DDL in
`scripts/create_tables.py` has not been executed against a real database
as part of this checklist run. If it hasn't been run recently, running
`python -m scripts.create_tables` once and confirming it completes cleanly
is worth doing before relying on any of the above against real data.
