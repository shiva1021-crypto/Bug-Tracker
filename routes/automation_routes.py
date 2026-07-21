"""HTTP handlers for the Automation Rules page.

Rule management is org-wide (a rule can be scoped to a project or apply to
every project), so unlike fields/versions there is no per-project id in
the URL -- the permission gate is simply "Admin/PM of this organization."
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from services import admin_service, automation_service, project_service, workflow_service
from utils.auth import current_user, login_required

automation_bp = Blueprint("automation", __name__)


def _form_context(user, form=None):
    form = form or {}
    return {
        "projects": project_service.list_projects(user["organization_id"]),
        "triggers": automation_service.TRIGGERS,
        "condition_operators": automation_service.CONDITION_OPERATORS,
        "action_types": automation_service.ACTION_TYPES,
        "statuses": workflow_service.STATUSES,
        "developers": workflow_service.list_assignable_developers(user["organization_id"]),
        "roles": admin_service.ROLES,
        "role_labels": admin_service.ROLE_LABELS,
        "form": form,
    }


@automation_bp.route("/automation", methods=["GET", "POST"])
@login_required
def list_rules():
    user = current_user()
    manager = automation_service.verify_automation_manager(user["id"])
    if manager is None:
        flash("You do not have permission to manage automation rules.", "error")
        return redirect(url_for("projects.list_projects"))

    if request.method == "GET":
        rules = automation_service.list_rules(user["organization_id"])
        return render_template(
            "automation/list.html",
            rules=rules,
            condition_summary=automation_service.condition_summary,
            action_summary=lambda rule: automation_service.action_summary(rule, user["organization_id"]),
            **_form_context(user),
        )

    form = request.form
    errors, cleaned = automation_service.validate_rule(
        organization_id=user["organization_id"],
        name=form.get("name", ""),
        project_id_raw=form.get("project_id", ""),
        trigger_event=form.get("trigger_event", ""),
        condition_fields=form.getlist("condition_field"),
        condition_operators=form.getlist("condition_operator"),
        condition_values=form.getlist("condition_value"),
        action_type=form.get("action_type", ""),
        action_status=form.get("action_status", ""),
        action_user_id_raw=form.get("action_user_id", ""),
        action_role=form.get("action_role", ""),
        action_comment_text=form.get("action_comment_text", ""),
    )
    if errors:
        for error in errors:
            flash(error, "error")
        rules = automation_service.list_rules(user["organization_id"])
        return (
            render_template(
                "automation/list.html",
                rules=rules,
                condition_summary=automation_service.condition_summary,
                action_summary=lambda rule: automation_service.action_summary(rule, user["organization_id"]),
                form_open=True,
                **_form_context(user, form),
            ),
            400,
        )

    automation_service.create_rule(user["organization_id"], cleaned)
    flash(f'Rule "{cleaned["name"]}" created.', "success")
    return redirect(url_for("automation.list_rules"))


@automation_bp.post("/automation/<int:rule_id>/toggle")
@login_required
def toggle_rule(rule_id):
    user = current_user()
    manager = automation_service.verify_automation_manager(user["id"])
    if manager is None:
        flash("You do not have permission to manage automation rules.", "error")
        return redirect(url_for("projects.list_projects"))

    ok, error = automation_service.toggle_rule(rule_id, user["organization_id"])
    if not ok:
        flash(error or "Could not update the rule.", "error")
    return redirect(url_for("automation.list_rules"))


@automation_bp.post("/automation/<int:rule_id>/delete")
@login_required
def delete_rule(rule_id):
    user = current_user()
    manager = automation_service.verify_automation_manager(user["id"])
    if manager is None:
        flash("You do not have permission to manage automation rules.", "error")
        return redirect(url_for("projects.list_projects"))

    rule = automation_service.get_rule(rule_id, user["organization_id"])
    if rule is None:
        flash("Rule not found.", "error")
        return redirect(url_for("automation.list_rules"))

    automation_service.delete_rule(rule_id, user["organization_id"])
    flash(f'Rule "{rule["name"]}" deleted.', "success")
    return redirect(url_for("automation.list_rules"))
