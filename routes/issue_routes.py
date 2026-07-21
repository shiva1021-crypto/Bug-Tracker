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
from services import (
    automation_service,
    custom_field_service,
    filter_service,
    issue_service,
    link_service,
    project_service,
    time_tracking_service,
    version_service,
    workflow_service,
)
from utils.auth import current_user, login_required

issue_bp = Blueprint("issues", __name__)


@issue_bp.get("/issues")
@login_required
def list_issues():
    """The Stage 8 issue list/search page.

    Not one of Stage 5-7's routes -- it did not exist before this stage,
    but Stage 8's own spec assumes an "Issue List page" to extend with
    filter chips and a save button. Added here as the minimal
    infrastructure that assumption requires, the same reasoning Stage 5
    used to add the project detail page's issue table (see
    STAGE-05-REPORT.md §5.7) and Stage 7 used to add the screenshot route
    (STAGE-05-REPORT.md §5.6): the feature this stage actually asks for
    (saved filters) has nothing to attach to without it.
    """
    user = current_user()
    filters = filter_service.parse_filters(request.args)
    results = filter_service.search(user["organization_id"], filters)
    saved_filters = filter_service.list_saved_filters(user["id"], user["organization_id"])

    return render_template(
        "issues/list.html",
        results=results,
        filters=filters,
        saved_filters=saved_filters,
        projects=project_service.list_projects(user["organization_id"]),
        statuses=workflow_service.STATUSES,
        priorities=issue_service.PRIORITIES,
        issue_types=issue_service.ISSUE_TYPES,
        org_users=issue_service.list_org_users(user["organization_id"]),
    )


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
    submitted_project_id = form.get("project_id", type=int) or 0
    errors, cleaned = issue_service.validate_issue(
        organization_id=user["organization_id"],
        project_id=submitted_project_id,
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
        fix_version_raw=form.get("fix_version_id", ""),
    )

    # Stage 9: custom field values are validated here (before the issue
    # exists) but only *persisted* after creation succeeds below --
    # `custom_field_service.save_values` needs a real issue id to attach
    # values to, which doesn't exist until `issue_service.create_issue`
    # returns one.
    errors.extend(
        custom_field_service.validate_values(submitted_project_id, user["organization_id"], form)
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
                selected_fix_version_id=form.get("fix_version_id", ""),
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
    custom_field_service.save_values(issue_id, user["organization_id"], project["id"], form)

    created_issue = issue_service.get_issue(issue_id, user["organization_id"])
    automation_service.execute_automation_rules(
        organization_id=user["organization_id"],
        project_id=project["id"],
        trigger_event="issue_created",
        context={"issue": created_issue},
        actor_user_id=user["id"],
    )

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

    can_change_status = workflow_service.can_update_status(user["id"], issue) is not None
    can_assign = workflow_service.can_assign(user["id"]) is not None
    assignable_developers = (
        workflow_service.list_assignable_developers(user["organization_id"]) if can_assign else []
    )
    comments = workflow_service.list_comments(issue_id, user["organization_id"])
    history = workflow_service.list_history(issue_id, user["organization_id"])
    watching = workflow_service.is_watching(issue_id, user["id"])
    watcher_count = workflow_service.watcher_count(issue_id)
    links = link_service.list_links(issue_id, user["organization_id"])

    custom_field_values = custom_field_service.list_values_for_issue(issue_id, user["organization_id"])

    time_entries = time_tracking_service.list_entries(issue_id, user["organization_id"])
    time_spent = time_tracking_service.total_spent(time_entries)

    fix_version = (
        version_service.get_version(issue["fix_version_id"], user["organization_id"])
        if issue["fix_version_id"]
        else None
    )

    return render_template(
        "issues/detail.html",
        issue=issue,
        children=children,
        can_edit=editor is not None,
        statuses=workflow_service.STATUSES,
        can_change_status=can_change_status,
        can_assign=can_assign,
        assignable_developers=assignable_developers,
        comments=comments,
        history=history,
        watching=watching,
        watcher_count=watcher_count,
        links=links,
        link_form_options=link_service.LINK_FORM_OPTIONS,
        custom_field_values=custom_field_values,
        time_entries=time_entries,
        time_spent=time_spent,
        fix_version=fix_version,
    )


@issue_bp.post("/issues/<int:issue_id>/status")
@login_required
def change_status(issue_id):
    user = current_user()
    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None:
        abort(404)

    permitted_user = workflow_service.can_update_status(user["id"], issue)
    if permitted_user is None:
        flash("You do not have permission to change this issue's status.", "error")
        return redirect(url_for("issues.issue_detail", issue_id=issue_id))

    old_status = issue["status"]
    new_status = request.form.get("status", "")
    ok, error = workflow_service.change_status(issue, new_status, permitted_user)
    if ok and new_status != old_status:
        updated_issue = issue_service.get_issue(issue_id, user["organization_id"])
        automation_service.execute_automation_rules(
            organization_id=user["organization_id"],
            project_id=issue["project_id"],
            trigger_event="status_changed",
            context={"issue": updated_issue, "old_status": old_status, "new_status": new_status},
            actor_user_id=permitted_user["id"],
        )
    flash("Status updated." if ok else (error or "Could not update status."),
          "success" if ok else "error")
    return redirect(url_for("issues.issue_detail", issue_id=issue_id))


@issue_bp.post("/issues/<int:issue_id>/assign")
@login_required
def assign_issue(issue_id):
    user = current_user()
    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None:
        abort(404)

    permitted_user = workflow_service.can_assign(user["id"])
    if permitted_user is None:
        flash("You do not have permission to assign this issue.", "error")
        return redirect(url_for("issues.issue_detail", issue_id=issue_id))

    old_status = issue["status"]
    assigned_to_raw = request.form.get("assigned_to", "")
    ok, error = workflow_service.assign_issue(
        issue, assigned_to_raw, permitted_user, user["organization_id"]
    )
    if ok:
        # `assign_issue` can auto-transition To Do -> In Progress; only
        # fire `status_changed` automation when that actually happened,
        # not on every assignment (a plain reassignment with no status
        # change should not trigger status-based rules).
        updated_issue = issue_service.get_issue(issue_id, user["organization_id"])
        if updated_issue["status"] != old_status:
            automation_service.execute_automation_rules(
                organization_id=user["organization_id"],
                project_id=issue["project_id"],
                trigger_event="status_changed",
                context={
                    "issue": updated_issue,
                    "old_status": old_status,
                    "new_status": updated_issue["status"],
                },
                actor_user_id=permitted_user["id"],
            )
    flash("Assignment updated." if ok else (error or "Could not update assignment."),
          "success" if ok else "error")
    return redirect(url_for("issues.issue_detail", issue_id=issue_id))


@issue_bp.post("/issues/<int:issue_id>/comment")
@login_required
def add_comment(issue_id):
    user = current_user()
    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None:
        abort(404)

    text = request.form.get("comment", "")
    ok, error = workflow_service.add_comment(issue_id, user["id"], text)
    if not ok:
        flash(error or "Could not add comment.", "error")
    return redirect(url_for("issues.issue_detail", issue_id=issue_id))


@issue_bp.post("/issues/<int:issue_id>/watch")
@login_required
def toggle_watch(issue_id):
    user = current_user()
    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None:
        abort(404)

    workflow_service.toggle_watch(issue_id, user["id"])
    return redirect(url_for("issues.issue_detail", issue_id=issue_id))


@issue_bp.post("/issues/<int:issue_id>/link")
@login_required
def add_link(issue_id):
    user = current_user()
    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None:
        abort(404)

    ok, error = link_service.create_link(
        user["organization_id"],
        issue,
        request.form.get("link_type", ""),
        request.form.get("target_key", ""),
    )
    flash("Link added." if ok else (error or "Could not add link."),
          "success" if ok else "error")
    return redirect(url_for("issues.issue_detail", issue_id=issue_id))


@issue_bp.post("/issues/<int:issue_id>/link/<int:link_id>/remove")
@login_required
def remove_link(issue_id, link_id):
    user = current_user()
    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None:
        abort(404)

    ok, error = link_service.remove_link(link_id, issue_id, user["organization_id"])
    flash("Link removed." if ok else (error or "Could not remove link."),
          "success" if ok else "error")
    return redirect(url_for("issues.issue_detail", issue_id=issue_id))


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
        custom_fields = custom_field_service.list_values_for_issue(issue_id, user["organization_id"])
        selectable_versions = version_service.list_selectable_versions(
            issue["project_id"], user["organization_id"]
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
            custom_fields=custom_fields,
            selectable_versions=selectable_versions,
            selected_fix_version_id=issue["fix_version_id"],
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
        fix_version_raw=form.get("fix_version_id", ""),
        current_issue_id=issue_id,
    )

    # Same reasoning as `add_issue`: validate custom field values before
    # touching the database, so a bad custom field value doesn't leave the
    # standard fields updated while the custom ones silently didn't save
    # (or vice versa) -- everything for one edit submission succeeds or
    # fails together.
    errors.extend(
        custom_field_service.validate_values(issue["project_id"], user["organization_id"], form)
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
        custom_fields = custom_field_service.list_values_for_issue(issue_id, user["organization_id"])
        selectable_versions = version_service.list_selectable_versions(
            issue["project_id"], user["organization_id"]
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
                custom_fields=custom_fields,
                selectable_versions=selectable_versions,
                selected_fix_version_id=form.get("fix_version_id", ""),
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

    issue_service.update_issue(
        issue_id, user["organization_id"], cleaned, final_screenshot_path, user["id"]
    )
    if old_path_to_delete:
        issue_service.delete_screenshot_file(old_path_to_delete)

    _errors_ignored, field_changes = custom_field_service.save_values(
        issue_id, user["organization_id"], issue["project_id"], form
    )

    if field_changes:
        updated_issue = issue_service.get_issue(issue_id, user["organization_id"])
        for change in field_changes:
            automation_service.execute_automation_rules(
                organization_id=user["organization_id"],
                project_id=issue["project_id"],
                trigger_event="field_updated",
                context={
                    "issue": updated_issue,
                    "field_name": change["field_name"],
                    "old_value": change["old_value"],
                    "new_value": change["new_value"],
                },
                actor_user_id=user["id"],
            )

    flash(f'Issue "{issue["issue_key"]}" updated.', "success")
    return redirect(url_for("issues.issue_detail", issue_id=issue_id))


@issue_bp.post("/issues/<int:issue_id>/time")
@login_required
def log_time(issue_id):
    user = current_user()
    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None:
        abort(404)

    ok, error = time_tracking_service.log_time(
        issue_id, user["id"], request.form.get("hours_spent", ""), request.form.get("description", "")
    )
    flash("Time logged." if ok else (error or "Could not log time."), "success" if ok else "error")
    return redirect(url_for("issues.issue_detail", issue_id=issue_id))


@issue_bp.post("/issues/<int:issue_id>/estimate")
@login_required
def update_estimate(issue_id):
    user = current_user()
    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None:
        abort(404)

    editor = issue_service.get_editor_permission(user["id"], issue)
    if editor is None:
        flash("You do not have permission to update this issue's estimate.", "error")
        return redirect(url_for("issues.issue_detail", issue_id=issue_id))

    ok, error = time_tracking_service.update_estimate(
        issue_id,
        user["organization_id"],
        request.form.get("time_estimate", ""),
        request.form.get("time_remaining", ""),
    )
    flash("Estimate updated." if ok else (error or "Could not update estimate."), "success" if ok else "error")
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
