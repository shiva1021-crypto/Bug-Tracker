"""HTTP handlers for the projects list, project creation and a placeholder
project detail page.

Every route is organization-scoped: the list only ever shows the caller's
own organization's projects and a project id belonging to another
organization behaves exactly like a nonexistent one -- redirected with a
generic "not found," no information about other organizations leaks out.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from services import issue_service, project_service
from utils.auth import current_user, login_required

project_bp = Blueprint("projects", __name__)


@project_bp.get("/projects")
@login_required
def list_projects():
    user = current_user()
    projects = project_service.list_projects(user["organization_id"])
    return render_template("projects/list.html", projects=projects)


@project_bp.post("/projects/create")
@login_required
def create_project():
    user = current_user()
    creator = project_service.verify_project_creator(user["id"])
    if creator is None:
        flash("You do not have permission to create a project.", "error")
        return redirect(url_for("projects.list_projects"))

    name = request.form.get("name", "")
    project_key = request.form.get("project_key", "")
    description = request.form.get("description", "")

    errors = project_service.validate_project(name, project_key, creator["organization_id"])
    if errors:
        for error in errors:
            flash(error, "error")
        projects = project_service.list_projects(creator["organization_id"])
        # Re-render with the form re-opened and the entered values retained.
        return (
            render_template(
                "projects/list.html",
                projects=projects,
                form_open=True,
                name=name,
                project_key=project_key,
                description=description,
            ),
            400,
        )

    project_service.create_project(creator["organization_id"], name, project_key, description)
    flash(f'Project "{name.strip()}" created.', "success")
    return redirect(url_for("projects.list_projects"))


@project_bp.get("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    user = current_user()
    project = project_service.get_project(project_id, user["organization_id"])
    if project is None:
        flash("Project not found.", "error")
        return redirect(url_for("projects.list_projects"))
    # There is no board yet (that's a later stage), so this page is also
    # the only place to browse a project's issues -- without this, an
    # issue created via /issues/add would have no link to reach it from
    # again except a direct URL.
    issues = issue_service.list_by_project(project_id, user["organization_id"])
    return render_template("projects/detail.html", project=project, issues=issues)
