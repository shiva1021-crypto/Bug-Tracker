"""HTTP handlers for the configurable dashboard -- the default landing
page after login (see `routes/auth_routes.py`'s login/register success
redirects).
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from services import dashboard_service
from utils.auth import current_user, login_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/dashboard")
@login_required
def dashboard():
    user = current_user()
    # Defensive: an organization created before Stage 10 existed would
    # otherwise have no default widgets at all. Idempotent, so this is
    # cheap to call on every view.
    dashboard_service.ensure_org_defaults(user["organization_id"])

    widgets = dashboard_service.get_layout(user["organization_id"], user["id"])
    rendered_widgets = [
        {**widget, "data": dashboard_service.widget_data(widget, user["organization_id"])}
        for widget in widgets
    ]

    return render_template(
        "dashboard.html",
        widgets=rendered_widgets,
        widget_types=dashboard_service.WIDGET_TYPES,
        widget_labels=dashboard_service.WIDGET_LABELS,
        widths=dashboard_service.WIDTHS,
    )


@dashboard_bp.post("/dashboard/widgets/add")
@login_required
def add_widget():
    user = current_user()
    form = request.form

    errors, cleaned = dashboard_service.validate_widget(
        form.get("widget_type", ""), form.get("title", ""), form.get("width", "half")
    )
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("dashboard.dashboard"))

    dashboard_service.add_widget(user["organization_id"], user["id"], cleaned)
    flash(f'Widget "{cleaned["title"]}" added.', "success")
    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.post("/dashboard/widgets/<int:widget_id>/remove")
@login_required
def remove_widget(widget_id):
    user = current_user()
    ok = dashboard_service.remove_widget(user["organization_id"], user["id"], widget_id)
    if not ok:
        flash("Widget not found.", "error")
    return redirect(url_for("dashboard.dashboard"))
