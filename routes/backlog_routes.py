"""HTTP handlers for the Stage 8 backlog page and sprint lifecycle.

Creating, starting, and closing a sprint, and moving an issue between the
backlog and a sprint, are all gated by `sprint_service.verify_sprint_manager()`
-- the same fresh-DB-read permission pattern used everywhere else in this
codebase. Every redirect target tries to keep the user on the same
project's backlog view they started from, since this page is always
scoped to one project at a time.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from services import burndown_service, issue_service, project_service, sprint_service
from utils.auth import current_user, login_required

backlog_bp = Blueprint("backlog", __name__)


@backlog_bp.get("/backlog")
@login_required
def backlog():
    user = current_user()
    projects = project_service.list_projects(user["organization_id"])

    requested_project_id = request.args.get("project", type=int)
    project = None
    if requested_project_id is not None:
        project = project_service.get_project(requested_project_id, user["organization_id"])
    if project is None and projects:
        project = projects[0]

    can_manage = sprint_service.verify_sprint_manager(user["id"]) is not None

    backlog_issues = []
    sprint_sections = []
    if project is not None:
        backlog_issues = sprint_service.list_backlog(user["organization_id"], project["id"])

        for sprint in sprint_service.list_open_sprints(user["organization_id"], project["id"]):
            sprint_issues = sprint_service.list_sprint_issues(sprint["id"], user["organization_id"])
            burndown = None
            if sprint["status"] == "active":
                burndown = burndown_service.compute_burndown(
                    sprint, sprint_issues, user["organization_id"]
                )
            sprint_sections.append(
                {
                    "sprint": sprint,
                    "issues": sprint_issues,
                    "points_total": sprint_service.total_story_points(sprint_issues),
                    "burndown": burndown,
                }
            )

    return render_template(
        "backlog.html",
        projects=projects,
        selected_project=project,
        can_manage=can_manage,
        backlog_issues=backlog_issues,
        sprint_sections=sprint_sections,
    )


def _redirect_to_backlog(project_id: int | None):
    if project_id is not None:
        return redirect(url_for("backlog.backlog", project=project_id))
    return redirect(url_for("backlog.backlog"))


@backlog_bp.post("/sprints/create")
@login_required
def create_sprint():
    user = current_user()
    project_id = request.form.get("project_id", type=int)

    manager = sprint_service.verify_sprint_manager(user["id"])
    if manager is None:
        flash("You do not have permission to create a sprint.", "error")
        return _redirect_to_backlog(project_id)

    project = project_service.get_project(project_id, user["organization_id"]) if project_id else None
    if project is None:
        flash("Select a valid project first.", "error")
        return _redirect_to_backlog(None)

    errors, cleaned = sprint_service.validate_sprint(
        request.form.get("name", ""),
        request.form.get("goal", ""),
        request.form.get("start_date", ""),
        request.form.get("end_date", ""),
    )
    if errors:
        for error in errors:
            flash(error, "error")
        return _redirect_to_backlog(project["id"])

    sprint_service.create_sprint(user["organization_id"], project["id"], cleaned)
    flash(f'Sprint "{cleaned["name"]}" created.', "success")
    return _redirect_to_backlog(project["id"])


@backlog_bp.post("/sprints/<int:sprint_id>/start")
@login_required
def start_sprint(sprint_id):
    user = current_user()
    sprint = sprint_service.get_sprint(sprint_id, user["organization_id"])
    if sprint is None:
        abort(404)

    manager = sprint_service.verify_sprint_manager(user["id"])
    if manager is None:
        flash("You do not have permission to start a sprint.", "error")
        return _redirect_to_backlog(sprint["project_id"])

    ok, error = sprint_service.start_sprint(sprint, manager)
    flash("Sprint started." if ok else (error or "Could not start the sprint."),
          "success" if ok else "error")
    return _redirect_to_backlog(sprint["project_id"])


@backlog_bp.post("/sprints/<int:sprint_id>/close")
@login_required
def close_sprint(sprint_id):
    user = current_user()
    sprint = sprint_service.get_sprint(sprint_id, user["organization_id"])
    if sprint is None:
        abort(404)

    manager = sprint_service.verify_sprint_manager(user["id"])
    if manager is None:
        flash("You do not have permission to close a sprint.", "error")
        return _redirect_to_backlog(sprint["project_id"])

    ok, error = sprint_service.close_sprint(sprint, manager)
    flash("Sprint closed." if ok else (error or "Could not close the sprint."),
          "success" if ok else "error")
    return _redirect_to_backlog(sprint["project_id"])


@backlog_bp.post("/issues/<int:issue_id>/sprint")
@login_required
def assign_sprint(issue_id):
    user = current_user()
    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None:
        abort(404)

    manager = sprint_service.verify_sprint_manager(user["id"])
    if manager is None:
        flash("You do not have permission to move issues between sprints.", "error")
        return _redirect_to_backlog(issue["project_id"])

    ok, error = sprint_service.assign_issue_to_sprint(
        issue, request.form.get("sprint_id", ""), user["organization_id"]
    )
    if not ok:
        flash(error or "Could not update the issue's sprint.", "error")
    return _redirect_to_backlog(issue["project_id"])
