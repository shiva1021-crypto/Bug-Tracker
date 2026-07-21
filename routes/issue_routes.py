"""HTTP handlers for creating, viewing, and editing issues, plus serving
stored screenshots.

`GET /issues/<id>` and its edit counterpart return a genuine 404 (not a
redirect-with-flash like `/projects/<id>`) when the id doesn't exist or
belongs to another organization -- the spec calls this out explicitly for
issues ("Viewing another organization's issue by guessing its ID returns
404, not the issue"), so both cases are handled identically via
`abort(404)`, and Flask's registered 404 handler renders one plain page
either way. No information about *why* it 404'd (wrong org vs. never
existed) is distinguishable from the response.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, send_from_directory, url_for

from config import config
from services import issue_service, project_service
from utils.auth import current_user, login_required

issue_bp = Blueprint("issues", __name__)


@issue_bp.route("/issues/add", methods=["GET", "POST"])
@login_required
def add_issue():
    user = current_user()
    projects = project_service.list_projects(user["organization_id"])

    if request.method == "GET":
        parent_candidates = issue_service.list_potential_parents(user["organization_id"])
        return render_template(
            "issues/add.html",
            projects=projects,
            parent_candidates=parent_candidates,
            issue_types=issue_service.ISSUE_TYPES,
            priorities=issue_service.PRIORITIES,
            severities=issue_service.SEVERITIES,
            preselect_project_id=request.args.get("project_id", type=int),
        )

    form = request.form
    errors, cleaned = issue_service.validate_issue(
        organization_id=user["organization_id"],
        project_id=form.get("project_id", type=int) or 0,
        issue_type=form.get("issue_type", ""),
        parent_id_raw=form.get("parent_id", ""),
        title=form.get("title", ""),
        description=form.get("description", ""),
        reproduction_steps=form.get("reproduction_steps", ""),
        category=form.get("category", ""),
        priority=form.get("priority", ""),
        severity=form.get("severity", ""),
        labels_raw=form.get("labels", ""),
        story_points_raw=form.get("story_points", ""),
        due_date_raw=form.get("due_date", ""),
    )

    screenshot_path, screenshot_error = issue_service.validate_and_store_screenshot(
        request.files.get("screenshot")
    )
    if screenshot_error:
        errors.append(screenshot_error)

    if errors:
        for error in errors:
            flash(error, "error")
        if screenshot_path:
            issue_service.delete_screenshot_file(screenshot_path)
        parent_candidates = issue_service.list_potential_parents(user["organization_id"])
        return (
            render_template(
                "issues/add.html",
                projects=projects,
                parent_candidates=parent_candidates,
                issue_types=issue_service.ISSUE_TYPES,
                priorities=issue_service.PRIORITIES,
                severities=issue_service.SEVERITIES,
                preselect_project_id=form.get("project_id", type=int),
                selected_issue_type=form.get("issue_type", ""),
                selected_parent_id=form.get("parent_id", ""),
                title=form.get("title", ""),
                description=form.get("description", ""),
                reproduction_steps=form.get("reproduction_steps", ""),
                category=form.get("category", ""),
                selected_priority=form.get("priority", ""),
                selected_severity=form.get("severity", ""),
                labels=form.get("labels", ""),
                story_points=form.get("story_points", ""),
                due_date=form.get("due_date", ""),
            ),
            400,
        )

    project = project_service.get_project(cleaned["project_id"], user["organization_id"])
    result = issue_service.create_issue(user["organization_id"], project, user["id"], cleaned, screenshot_path)
    if result is None:
        if screenshot_path:
            issue_service.delete_screenshot_file(screenshot_path)
        flash("Could not create the issue -- the project may no longer exist.", "error")
        return redirect(url_for("projects.list_projects"))

    issue_id, issue_key = result
    flash(f'Issue "{issue_key}" created.', "success")
    return redirect(url_for("issues.issue_detail", issue_id=issue_id))


@issue_bp.get("/issues/<int:issue_id>")
@login_required
def issue_detail(issue_id):
    user = current_user()
    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None:
        abort(404)

    editor = issue_service.get_editor_permission(user["id"], issue)
    children = issue_service.list_children(issue_id, user["organization_id"])
    return render_template(
        "issues/detail.html", issue=issue, children=children, can_edit=editor is not None
    )


@issue_bp.route("/issues/<int:issue_id>/edit", methods=["GET", "POST"])
@login_required
def edit_issue(issue_id):
    user = current_user()
    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None:
        abort(404)

    editor = issue_service.get_editor_permission(user["id"], issue)
    if editor is None:
        flash("You do not have permission to edit this issue.", "error")
        return redirect(url_for("issues.issue_detail", issue_id=issue_id))

    if request.method == "GET":
        parent_options = issue_service.list_valid_parents_for(
            user["organization_id"], issue["project_id"], issue["issue_type"], exclude_issue_id=issue_id
        )
        return render_template(
            "issues/edit.html",
            issue=issue,
            parent_options=parent_options,
            priorities=issue_service.PRIORITIES,
            severities=issue_service.SEVERITIES,
            selected_parent_id=issue["parent_id"],
            title=issue["title"],
            description=issue["description"],
            reproduction_steps=issue["reproduction_steps"],
            category=issue["category"],
            selected_priority=issue["priority"],
            selected_severity=issue["severity"],
            labels=issue["labels"],
            story_points=issue["story_points"],
            due_date=issue["due_date"].isoformat() if issue["due_date"] else "",
        )

    form = request.form
    errors, cleaned = issue_service.validate_issue(
        organization_id=user["organization_id"],
        project_id=issue["project_id"],  # fixed -- not user-editable, see issue_service docstring
        issue_type=issue["issue_type"],  # fixed -- not user-editable
        parent_id_raw=form.get("parent_id", ""),
        title=form.get("title", ""),
        description=form.get("description", ""),
        reproduction_steps=form.get("reproduction_steps", ""),
        category=form.get("category", ""),
        priority=form.get("priority", ""),
        severity=form.get("severity", ""),
        labels_raw=form.get("labels", ""),
        story_points_raw=form.get("story_points", ""),
        due_date_raw=form.get("due_date", ""),
        current_issue_id=issue_id,
    )

    remove_screenshot = form.get("remove_screenshot") == "on"
    new_screenshot_path, screenshot_error = issue_service.validate_and_store_screenshot(
        request.files.get("screenshot")
    )
    if screenshot_error:
        errors.append(screenshot_error)

    if errors:
        for error in errors:
            flash(error, "error")
        if new_screenshot_path:
            issue_service.delete_screenshot_file(new_screenshot_path)
        parent_options = issue_service.list_valid_parents_for(
            user["organization_id"], issue["project_id"], issue["issue_type"], exclude_issue_id=issue_id
        )
        return (
            render_template(
                "issues/edit.html",
                issue=issue,
                parent_options=parent_options,
                priorities=issue_service.PRIORITIES,
                severities=issue_service.SEVERITIES,
                selected_parent_id=form.get("parent_id", ""),
                title=form.get("title", ""),
                description=form.get("description", ""),
                reproduction_steps=form.get("reproduction_steps", ""),
                category=form.get("category", ""),
                selected_priority=form.get("priority", ""),
                selected_severity=form.get("severity", ""),
                labels=form.get("labels", ""),
                story_points=form.get("story_points", ""),
                due_date=form.get("due_date", ""),
            ),
            400,
        )

    final_screenshot_path = issue["screenshot_path"]
    old_path_to_delete = None
    if new_screenshot_path:
        old_path_to_delete = issue["screenshot_path"]
        final_screenshot_path = new_screenshot_path
    elif remove_screenshot:
        old_path_to_delete = issue["screenshot_path"]
        final_screenshot_path = None

    issue_service.update_issue(issue_id, user["organization_id"], cleaned, final_screenshot_path)
    if old_path_to_delete:
        issue_service.delete_screenshot_file(old_path_to_delete)

    flash(f'Issue "{issue["issue_key"]}" updated.', "success")
    return redirect(url_for("issues.issue_detail", issue_id=issue_id))


@issue_bp.get("/issues/<int:issue_id>/screenshot")
@login_required
def issue_screenshot(issue_id):
    """Stream a stored screenshot back to the browser.

    Not one of the spec's three listed routes, but required infrastructure:
    the file is stored outside `static/` (per the spec's own security
    requirement), so nothing can load it directly -- this route is the
    only path to it, and it re-checks organization membership exactly like
    every other issue lookup before streaming anything.
    """
    user = current_user()
    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None or not issue["screenshot_path"]:
        abort(404)
    return send_from_directory(config.SCREENSHOT_UPLOAD_DIR, issue["screenshot_path"])
