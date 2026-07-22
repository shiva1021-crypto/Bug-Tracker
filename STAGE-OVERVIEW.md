# Stage Overview

A one-page, at-a-glance summary of the 10 build stages. For full design
decisions, interpretation calls and verification results, see each
linked `STAGE-0N-REPORT.md`. For setup/run instructions, see `README.md`.

| # | Stage | Goal | Key Features | Main Pages | Status | Full Report |
|---|---|---|---|---|---|---|
| 1 | Foundation & Setup | Runnable skeleton: Flask app + pooled MySQL connection + health checks | App boot, DB connection pool, dev/prod env config, secret-key policy | - (JSON health endpoints only) | ✅ Complete | [STAGE-01-REPORT.md](STAGE-01-REPORT.md) |
| 2 | Authentication | Secure account creation, login/logout and session handling | Registration, hashed passwords, generic login errors, POST-only logout, `login_required`, profile page | Landing, Login, Register, Profile | ✅ Complete | [STAGE-02-REPORT.md](STAGE-02-REPORT.md) |
| 3 | Multi-Tenancy & Roles | Turn single-user login into a multi-organization system with roles | Org-scoped data on every query, new-org vs join-existing-org registration, admin approval queue, Admin/PM/Developer/Tester role matrix | Admin › Users | ✅ Complete | [STAGE-03-REPORT.md](STAGE-03-REPORT.md) |
| 4 | Projects & Issue Keys | Let an org split work into projects with short issue-key codes | Project CRUD (2-6 letter key), auto-incrementing per-project issue counter, default "General" project on org creation | Projects | ✅ Complete | [STAGE-04-REPORT.md](STAGE-04-REPORT.md) |
| 5 | Core Issue CRUD & Hierarchy | Create, view and edit issues with a Jira-style type hierarchy | Epic/Story/Task/Bug/Subtask types, parent-child + cycle validation, screenshot upload (content-verified, randomized filename), auto issue keys | Issues (Add / Edit / Detail / List) | ✅ Complete | [STAGE-05-REPORT.md](STAGE-05-REPORT.md) |
| 6 | Workflow & Status | Give every issue a defined lifecycle with a full audit trail | 5 statuses (Idea→To Do→In Progress→Testing→Done), assignee-only status changes, auto-transition on assignment, history log, threaded comments, watchers | Issue Detail (status / comments / history) | ✅ Complete | [STAGE-06-REPORT.md](STAGE-06-REPORT.md) |
| 7 | Kanban Board | Visual, drag-and-drop board view of active work | 4-column board, project filter, assignee quick-filter, group by assignee/priority/type, permission-checked drag-and-drop | Board | ✅ Complete | [STAGE-07-REPORT.md](STAGE-07-REPORT.md) |
| 8 | Agile Planning | Scrum-style sprint planning plus issue linking and saved filters | Backlog, sprint lifecycle (future→active→closed), burndown chart, typed issue links (blocks/relates/duplicates/clones), saved filter chips | Backlog, Issue Detail (links) | ✅ Complete | [STAGE-08-REPORT.md](STAGE-08-REPORT.md) |
| 9 | Extensibility | Let an org tailor the tool without code changes | Custom fields (5 types), automation rules (trigger + conditions + typed action), time tracking, release versions | Projects › Custom Fields, Automation, Releases | ✅ Complete | [STAGE-09-REPORT.md](STAGE-09-REPORT.md) |
| 10 | Reporting, Dashboards & Ops | Surface insight and make the app production-ready | Filterable reports with charts + CSV export + print view, configurable dashboard widgets, email outbox worker, login rate limiting, production WSGI entry point, friendly DB-outage page | Dashboard, Reports | ✅ Complete | [STAGE-10-REPORT.md](STAGE-10-REPORT.md) |

All 10 stages are built and their pages have additionally been hand-matched
to the original reference UI design (structure, classes and wording) -
see `README.md`'s "Project structure" section for what changed there and
each `STAGE-0N-REPORT.md` for where the real data model didn't support
something the reference design assumed.
