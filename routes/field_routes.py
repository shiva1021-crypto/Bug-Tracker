"""HTTP handlers for project-specific custom fields.

Follows `routes/project_routes.py`'s convention for a missing/foreign
project: flash + redirect to the projects list, not a bare 404.
"""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from services import custom_field_service, project_service
from utils.auth import current_user, login_required

field_bp = Blueprint("fields", __name__)


@field_bp.route("/projects/<int:project_id>/fields", methods=["GET", "POST"])
@login_required
def manage_fields(project_id):
    user = current_user()
    project = project_service.get_project(project_id, user["organization_id"])
    if project is None:
        flash("Project not found.", "error")
        return redirect(url_for("projects.list_projects"))

    manager = custom_field_service.verify_field_manager(user["id"])
    if manager is None:
        flash("You do not have permission to manage custom fields.", "error")
        return redirect(url_for("projects.project_detail", project_id=project_id))

    if request.method == "GET":
        fields = custom_field_service.list_fields(project_id, user["organization_id"])
        return render_template(
            "projects/fields.html",
            project=project,
            fields=fields,
            field_types=custom_field_service.FIELD_TYPES,
        )

    errors, cleaned = custom_field_service.validate_field(
        request.form.get("name", ""),
        request.form.get("field_type", ""),
        request.form.get("options", ""),
        request.form.get("required", ""),
    )
    if errors:
        for error in errors:
            flash(error, "error")
        fields = custom_field_service.list_fields(project_id, user["organization_id"])
        return (
            render_template(
                "projects/fields.html",
                project=project,
                fields=fields,
                field_types=custom_field_service.FIELD_TYPES,
                form_open=True,
                name=request.form.get("name", ""),
                selected_field_type=request.form.get("field_type", ""),
                options=request.form.get("options", ""),
            ),
            400,
        )

    custom_field_service.create_field(user["organization_id"], project_id, cleaned)
    flash(f'Field "{cleaned["name"]}" added.', "success")
    return redirect(url_for("fields.manage_fields", project_id=project_id))


@field_bp.post("/projects/<int:project_id>/fields/<int:field_id>/delete")
@login_required
def delete_field(project_id, field_id):
    """Not one of the spec's listed routes, but required infrastructure:
    the frontend section explicitly calls for "a delete button" next to
    each field in the list, and the spec's Definition of Done requires
    deleting a field to actually work end-to-end -- there is no route to
    do that without this one. Same reasoning already used in Stage 5 (the
    screenshot route) and Stage 8 (the issue list page).
    """
    user = current_user()
    project = project_service.get_project(project_id, user["organization_id"])
    if project is None:
        flash("Project not found.", "error")
        return redirect(url_for("projects.list_projects"))

    manager = custom_field_service.verify_field_manager(user["id"])
    if manager is None:
        flash("You do not have permission to manage custom fields.", "error")
        return redirect(url_for("projects.project_detail", project_id=project_id))

    field = custom_field_service.get_field(field_id, user["organization_id"])
    if field is None or field["project_id"] != project_id:
        flash("Field not found.", "error")
        return redirect(url_for("fields.manage_fields", project_id=project_id))

    custom_field_service.delete_field(field_id, user["organization_id"])
    flash(f'Field "{field["name"]}" deleted.', "success")
    return redirect(url_for("fields.manage_fields", project_id=project_id))


@field_bp.get("/api/fields")
@login_required
def api_fields():
    """JSON field list for the Add/Edit Issue form's dynamic loading.

    Returns an empty list (not a 404/error) for a missing or foreign
    `project_id` -- the client-side JS that calls this just wants "what
    fields, if any, apply here," and a bad/absent id has zero fields by
    definition.
    """
    user = current_user()
    project_id = request.args.get("project_id", type=int)
    if project_id is None:
        return jsonify([])

    project = project_service.get_project(project_id, user["organization_id"])
    if project is None:
        return jsonify([])

    fields = custom_field_service.list_fields(project_id, user["organization_id"])
    return jsonify(
        [
            {
                "id": f["id"],
                "name": f["name"],
                "field_type": f["field_type"],
                "options": f["options"],
                "required": f["required"],
            }
            for f in fields
        ]
    )
