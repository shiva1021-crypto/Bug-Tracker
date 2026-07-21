"""HTTP handlers for the Reports page and its CSV export -- Admin/PM only,
per the spec.
"""

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from services import issue_service, project_service, report_service, workflow_service
from utils.auth import current_user, login_required

report_bp = Blueprint("reports", __name__)


def _require_report_viewer():
    user = current_user()
    return report_service.verify_report_viewer(user["id"])


@report_bp.get("/reports")
@login_required
def reports():
    viewer = _require_report_viewer()
    if viewer is None:
        flash("You do not have permission to view reports.", "error")
        return redirect(url_for("dashboard.dashboard"))

    errors, filters = report_service.parse_filters(request.args)
    for error in errors:
        flash(error, "error")

    result = report_service.run_report(viewer["organization_id"], filters)

    return render_template(
        "reports.html",
        result=result,
        filters=request.args,
        projects=project_service.list_projects(viewer["organization_id"]),
        statuses=workflow_service.STATUSES,
        priorities=issue_service.PRIORITIES,
        issue_count=len(result["rows"]),
    )


@report_bp.get("/reports/export.csv")
@login_required
def export_csv():
    viewer = _require_report_viewer()
    if viewer is None:
        flash("You do not have permission to export reports.", "error")
        return redirect(url_for("dashboard.dashboard"))

    _errors, filters = report_service.parse_filters(request.args)
    result = report_service.run_report(viewer["organization_id"], filters)
    csv_text = report_service.rows_to_csv(result["rows"])

    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=issue_report.csv"},
    )
