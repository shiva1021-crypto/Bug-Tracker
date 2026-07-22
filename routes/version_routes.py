"""HTTP handlers for the Versions/Releases page.

Versions are project-scoped, but the spec's single `/versions` route (not
`/projects/<id>/versions`) lists every project's versions together and
lets the "+ New Version" form pick a project -- mirroring how `/automation`
is one page covering every project rather than one page per project.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from services import project_service, version_service
from utils.auth import current_user, login_required

version_bp = Blueprint("versions", __name__)


@version_bp.route("/versions", methods=["GET", "POST"])
@login_required
def list_versions():
    user = current_user()
    projects = project_service.list_projects(user["organization_id"])

    if request.method == "GET":
        versions_by_project = []
        for project in projects:
            versions = version_service.list_visible_versions(project["id"], user["organization_id"])
            versions_by_project.append(
                {
                    "project": project,
                    "versions": [
                        {"version": v, "counts": version_service.issue_counts(v["id"], user["organization_id"])}
                        for v in versions
                    ],
                }
            )
        return render_template(
            "versions/list.html",
            projects=projects,
            versions_by_project=versions_by_project,
            can_manage=version_service.verify_version_manager(user["id"]) is not None,
        )

    manager = version_service.verify_version_manager(user["id"])
    if manager is None:
        flash("You do not have permission to create versions.", "error")
        return redirect(url_for("versions.list_versions"))

    form = request.form
    project_id = form.get("project_id", type=int)
    project = project_service.get_project(project_id, user["organization_id"]) if project_id else None
    if project is None:
        flash("Select a valid project.", "error")
        return redirect(url_for("versions.list_versions"))

    errors, cleaned = version_service.validate_version(form.get("name", ""), form.get("release_date", ""))
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("versions.list_versions"))

    ok, error = version_service.create_version(user["organization_id"], project["id"], cleaned)
    if not ok:
        flash(error, "error")
        return redirect(url_for("versions.list_versions"))

    flash(f'Version "{cleaned["name"]}" created.', "success")
    return redirect(url_for("versions.list_versions"))


@version_bp.post("/versions/<int:version_id>/release")
@login_required
def release_version(version_id):
    user = current_user()
    manager = version_service.verify_version_manager(user["id"])
    if manager is None:
        flash("You do not have permission to release versions.", "error")
        return redirect(url_for("versions.list_versions"))

    version = version_service.get_version(version_id, user["organization_id"])
    if version is None:
        flash("Version not found.", "error")
        return redirect(url_for("versions.list_versions"))

    ok, error = version_service.release_version(version, manager)
    flash(f'Version "{version["name"]}" released.' if ok else (error or "Could not release version."),
          "success" if ok else "error")
    return redirect(url_for("versions.list_versions"))


@version_bp.post("/versions/<int:version_id>/archive")
@login_required
def archive_version(version_id):
    user = current_user()
    manager = version_service.verify_version_manager(user["id"])
    if manager is None:
        flash("You do not have permission to archive versions.", "error")
        return redirect(url_for("versions.list_versions"))

    version = version_service.get_version(version_id, user["organization_id"])
    if version is None:
        flash("Version not found.", "error")
        return redirect(url_for("versions.list_versions"))

    ok, error = version_service.archive_version(version, manager)
    flash(f'Version "{version["name"]}" archived.' if ok else (error or "Could not archive version."),
          "success" if ok else "error")
    return redirect(url_for("versions.list_versions"))


@version_bp.get("/api/versions")
@login_required
def api_versions():
    """JSON selectable-version list for the Add/Edit Issue form's Fix
    Version dropdown, loaded via AJAX on project change -- the same
    pattern the spec asks for with custom fields and necessary for the
    same reason: which versions are valid depends on which project is
    selected and that can change after the page has already loaded.
    """
    user = current_user()
    project_id = request.args.get("project_id", type=int)
    if project_id is None:
        return {"versions": []}

    project = project_service.get_project(project_id, user["organization_id"])
    if project is None:
        return {"versions": []}

    versions = version_service.list_selectable_versions(project_id, user["organization_id"])
    return {"versions": [{"id": v["id"], "name": v["name"]} for v in versions]}
