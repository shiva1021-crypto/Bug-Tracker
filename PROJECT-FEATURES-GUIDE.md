# Project Features Guide

Every feature in the app, what it does and why it was built the way it was.
Organized by feature area rather than by build stage - see the numbered
`STAGE-0N-REPORT.md` files and `STAGE-OVERVIEW.md` if you want the
stage-by-stage build history and full technical verification detail instead.

---

## 1. Accounts, organizations & login

**What it does:** Anyone can create an account at `/register`. If the
organization name they type doesn't exist yet, they instantly become that
organization's Admin. If the organization name already exists, no account is
created yet - instead a request is filed and they land on a "waiting for
approval" page. An existing Admin approves or rejects the request from
**Admin → Users**. Logging in requires a verified email/password pair;
logging out is a one-click action.

**Why it works this way:** The app is multi-tenant - many separate
organizations share the same running app and database, but must never see
each other's data. Making "does this org already exist" the fork in the road
(new org vs. join request) is what keeps a second person from silently
creating a duplicate organization by mistake and it's what forces someone
joining an existing team through an approval step rather than walking
straight in.

A few deliberate security choices worth knowing:
- Wrong password and "no such email" show the **exact same** error message.
  If they showed different messages, anyone could use the login form to
  discover which email addresses have accounts.
- Logging out only works via a specific button (a form submission), not a
  plain link. A plain link can be triggered by another website without the
  user's knowledge; a form submission can't.
- Passwords are never stored as typed - they're scrambled (hashed) with a
  one-way algorithm before touching the database, so even direct database
  access never reveals a real password.

---

## 2. Roles & permissions

**What it does:** Every user has exactly one of four roles: **Admin**,
**Project Manager**, **Developer**, or **Tester**. Roles control what a
person can do - for example, only Admin/PM can create projects, manage
sprints, or set up automation rules; a Developer can only change the status
of issues assigned to them; Admin can override almost anything.

**Why it works this way:** Rather than trusting "what role does this
person's login session say they are," every sensitive action re-checks the
person's role directly from the database at the moment they try to do it.
This matters because roles can change mid-session - if an Admin demotes
someone from Project Manager to Tester while that person is still logged
in, the change takes effect on their very next click, not the next time they
log in. It also means a technically-savvy user can't bypass a button that's
hidden from them in the UI and submit the underlying request directly -
the same check runs on the server either way.

---

## 3. Projects & issue keys

**What it does:** Each organization organizes its work into projects (for
example "Web Platform" with the key `WEB`). Every project gets a short,
uppercase key and every issue created inside it gets a sequential number
appended to that key (`WEB-1`, `WEB-2`, …) - the familiar Jira-style
identifier. A brand-new organization automatically gets one starter project
called "General" so there's always somewhere to create an issue right away.

**Why it works this way:** Two different organizations can each have their
own `WEB` project with no conflict, because the key only has to be unique
*within* one organization, not across the whole app. Issue numbers are
handed out safely even if two people create issues in the same project at
the exact same instant - the database briefly locks that project's counter
during the handoff, so numbers can never be skipped or duplicated under
pressure.

---

## 4. Issues (create, view, edit, hierarchy)

**What it does:** An issue can be one of five types - **Epic, Story, Task,
Bug, or Subtask** - and issues can be nested (a Story can belong to an
Epic, a Subtask can belong to a Story). Every issue has a title,
description, priority, severity, category, labels, an optional due date,
and an optional screenshot. Once created, an issue's project and type can
no longer be changed (see below for why).

**Why it works this way:** The parent/child hierarchy has rules - a
Subtask can't be a top-level issue, an Epic can't have a parent and a
child issue must belong to the same project as its parent. These rules are
enforced once, in one place, so there's no way to sneak an invalid
combination in through a different form or a direct request.

Project and issue type are locked after creation on purpose: the issue's
key already has the project's prefix baked into it (`WEB-3` would be
confusing sitting inside the `MOB` project) and changing an issue's type
after the fact could orphan its existing children (turning a Story with
Subtasks underneath it into a Task, which isn't allowed to have children at
all).

Screenshots are a special case worth knowing about: the app doesn't trust
a file's name or extension to decide whether it's really an image - it
opens the file and inspects its actual content. A text file renamed to
`screenshot.png` is rejected. Accepted screenshots are also stored under a
randomly generated filename, outside the folder the web server exposes
directly and can only be viewed through a route that re-checks you're
allowed to see that issue first.

Viewing or editing an issue that belongs to a different organization (or
doesn't exist at all) always shows the exact same "not found" page - this
prevents someone from learning "this ID exists, it's just not mine" by
guessing numbers in the URL.

---

## 5. Workflow & status

**What it does:** Every issue moves through five statuses in order:
**Idea → To Do → In Progress → Testing → Done**. Only the assigned
Developer (or an Admin/PM, as an override) can change an issue's status.
Assigning an unassigned "To Do" issue to someone automatically bumps it to
"In Progress" - the moment a developer is handed a task, it's understood
to be actively picked up. Every status change, assignment and edit is
recorded in a visible history log on the issue. Issues also support
threaded comments and a "watch" toggle so a user gets notified of future
activity on an issue they care about.

**Why it works this way:** Keeping the status column an open text field
(rather than a fixed, hard-coded list at the database level) was a
deliberate choice so a future version of the app could support custom,
per-organization workflows without a database change. Any permitted user
can currently move an issue directly to any of the five statuses (not just
the "next" one in sequence) - there's no enforced linear path today, only
a role restriction on *who* can make the change.

---

## 6. Kanban board

**What it does:** A drag-and-drop visual board with four columns - To Do,
In Progress, Testing, Done ("Idea" issues never appear here, since they
haven't been picked up yet). You can filter the board to one project,
group cards inside each column by assignee, priority, or issue type and
click a teammate's avatar to instantly filter the board down to just their
cards.

**Why it works this way:** Dragging a card triggers the exact same
permission check and status-change logic as changing status from an
issue's own detail page - there's only one gatekeeper for "is this status
change allowed," so dragging a card as an unauthorized user is rejected by
the server and the card visually snaps back, even though the drag looked
successful for a moment on screen. Grouping only affects how cards are
organized *inside* each of the four columns - it never adds or removes a
column.

---

## 7. Backlog & sprints (agile planning)

**What it does:** Each project has a backlog of unscheduled issues.
Admin/PM can create a sprint, start it (only one sprint per project can be
active at a time), move issues in and out of it and close it when it's
done. An active sprint shows a real burndown chart - a line showing how
much work is left, day by day, computed from the issue's actual status
history rather than a fake straight line.

**What else this area includes:** Issues can be linked to each other with
a typed relationship (blocks / relates to / duplicates / clones) and
there's a dedicated **Issues** page for filtering issues by project,
status, priority, or assignee - with the ability to save a particular
filter combination as a named shortcut for later.

**Why it works this way:** Only one sprint can be "active" per project at
a time, which mirrors how real Scrum teams work - you're always focused on
one current sprint, not several overlapping ones. The burndown chart's
"actual" line is rebuilt from the same audit-trail log the workflow
feature already keeps (see section 5), rather than a separate tracking
system, so it can't drift out of sync with what the status history
actually shows. A closed sprint currently has no page to revisit it -
once closed, its issues and history still exist, but there's no
dedicated "past sprints" view yet.

---

## 8. Custom fields

**What it does:** Admin/PM can add extra fields to a project beyond the
built-in ones - for example a "Environment" dropdown with
Staging/Production options, or a "Customer Impact" text field. Once added,
that field shows up on every issue in that project and can be filled in
when creating or editing an issue.

**Why it works this way:** This lets each organization tailor the tool to
their own process without needing a code change or a new database column
for every possible field someone might want. If a custom field definition
is deleted, any values already saved for it disappear automatically along
with it - the database itself guarantees that cleanup, so there's no
leftover orphaned data.

---

## 9. Automation rules

**What it does:** Admin/PM can set up "if this, then that" rules per
project - for example, "when status changes to Testing, add a comment,"
or "when an issue is created, assign it to a random developer." A rule has
a trigger (issue created / status changed / a custom field changed), an
optional set of conditions that must all match and one action to perform.
Rules can be turned on/off or deleted (there's currently no dedicated
"edit" screen - turning a rule off and creating a replacement covers the
same need).

**Why it works this way:** Automated actions bypass the normal
"is this specific person allowed to do this right now" permission check,
by design - that check already happened once, when an Admin/PM configured
the rule in the first place. Every automated change still writes to the
same history log a manual change would, so nothing an automation rule does
is any less visible or auditable than a person doing it by hand. Dragging
a card on the board and changing status from the issue detail page both
trigger the same automation - so a rule can't be quietly bypassed by using
one entry point instead of the other.

---

## 10. Time tracking

**What it does:** Anyone who can view an issue can log hours spent on it,
with an optional note. An issue can also carry an original time estimate.
The issue detail page always shows the live total of every logged entry.

**Why it works this way:** The total is always calculated fresh from the
individual log entries rather than stored and cached separately - so it's
never possible for the displayed total to fall out of sync with what was
actually logged.

---

## 11. Releases (versions)

**What it does:** Each project can define named release versions (e.g.
"v1.2"), each with a release date and a status (unreleased / released /
archived). An issue can be tagged with a target "fix version." The
Releases page shows every project's versions with a live count of open vs.
resolved issues against each one.

**Why it works this way:** Archiving a version only hides it from the main
list - it doesn't delete it or disturb the historical record on any issue
that was already tagged with it, so old release data stays intact and
traceable even after a version is no longer active.

---

## 12. Dashboard

**What it does:** A per-user, widget-based homepage shown right after
login. Widgets include a stats summary, breakdowns by status/priority/
severity/type (shown as charts) and a recent-issues list. A new
organization gets a sensible default set of widgets automatically; any
user can add or remove widgets from their own view without affecting
anyone else's.

**Why it works this way:** Every organization gets one shared "default"
layout and an individual user only gets their own personal copy of it the
*first* time they actually customize something (add or remove a widget).
This keeps "the org's default dashboard" easy to reason about - it's one
set of rows, not silently duplicated into every single user's account the
moment they sign up - while still letting each person end up with their
own personalized layout once they touch it.

---

## 13. Reports

**What it does:** Admin/PM can view filterable charts (by status,
priority and category) across a date range, project, status, or priority,
export the exact same filtered result set as a CSV file and print a
clean, sidebar-free version of the page.

**Why it works this way:** The chart data and the CSV export are both
generated from the exact same underlying query and the exact same filters
- so what you see on screen and what you download always match, even if
someone changes a filter and re-exports a moment later. Every exported
field - even ones that would normally be totally safe, like a status name
- is passed through a safety filter that neutralizes anything that looks
like a spreadsheet formula (a common trick used to smuggle commands into
CSV files that get opened in Excel). This costs nothing and removes any
need to worry about which columns might theoretically become risky in the
future.

---

## 14. Notifications (email)

**What it does:** The app queues an email whenever an issue is assigned,
an issue's status changes, or a registration request is approved/rejected.
A background worker checks that queue periodically and actually sends the
emails via whatever SMTP server is configured.

**Why it works this way:** Queuing an email (a fast database write) is
completely separate from actually sending it (a slower, less reliable
network operation) - so a user assigning an issue or changing its status
never has to wait on an email server and if no email server is configured
at all, the app still works perfectly; queued emails just sit there
un-sent instead of erroring out. This also means a temporary outage of the
email server never blocks or slows down the rest of the app.

---

## 15. Login/registration rate limiting

**What it does:** Repeated failed login or registration attempts from the
same source get temporarily blocked, to slow down automated
password-guessing.

**Why it works this way:** Only *failed* attempts count against the
limit - a successful login immediately clears your own counter, so a real
user who just mistyped their password once or twice is never penalized
the way a genuine attacker repeatedly guessing would be. This can run
purely in memory (simplest, resets whenever the app restarts) or backed by
the database (survives restarts and works correctly if the app is ever run
as multiple instances at once) - configurable via `.env`, no code change
needed to switch.

---

## 16. Error handling

**What it does:** A missing/expired security token shows a clean error
page instead of a crash. An issue or page you're not allowed to see (or
that doesn't exist) shows a proper "not found" page. If the database
itself becomes unreachable, the app shows a friendly explanation page with
the exact steps to fix it, instead of an unreadable technical crash.

**Why it works this way:** None of these situations should ever show a
raw Python error/stack trace to an end user - every one of them is caught
deliberately and turned into a normal-looking page with a clear next step.

---

## 17. Running in production

**What it does:** The app can run in two modes - a development mode
(`python run.py`, auto-reloads on code changes, more verbose errors) and a
production mode (a dedicated WSGI server: Waitress or Gunicorn, per the
included `Procfile`/`wsgi.py`).

**Why it works this way:** In production, the app refuses to even start
up if its session-signing secret key is missing, too short, or looks like
a leftover placeholder value - this is a deliberate hard stop, because a
weak or guessable secret key would let an attacker forge login sessions.
In development, a key is generated automatically and saved locally so
restarting the app during testing doesn't invalidate every open session.
