"""HTTP handlers for the admin panel: member list, role changes and
registration-request approval/rejection.

Every route here is gated by `_require_admin()`, which re-checks the
caller's role against the database on every single request (see
`services/admin_service.py::verify_admin`) rather than trusting the role
cached in the session at login. That is what makes a role downgrade take
effect immediately instead of only at the demoted user's next login.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from services import admin_service
from utils.auth import current_user, login_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _require_admin() -> dict | None:
    """Return the fresh admin user row, or None if the caller is not (or is
    no longer) an admin of their organization."""
    user = current_user()
    if user is None:
        return None
    return admin_service.verify_admin(user["id"])


@admin_bp.get("/users")
@login_required
def users_page():
    admin_user = _require_admin()
    if admin_user is None:
        flash("You do not have permission to view that page.", "error")
        return redirect(url_for("auth.profile"))

    users = admin_service.list_users(admin_user["organization_id"])
    pending = admin_service.list_pending_requests(admin_user["organization_id"])
    return render_template(
        "admin/users.html",
        users=users,
        pending=pending,
        roles=admin_service.ROLES,
        role_labels=admin_service.ROLE_LABELS,
    )


@admin_bp.post("/users/<int:user_id>/role")
@login_required
def change_role(user_id):
    admin_user = _require_admin()
    if admin_user is None:
        flash("You do not have permission to do that.", "error")
        return redirect(url_for("auth.profile"))

    new_role = request.form.get("role", "")
    ok, error = admin_service.change_role(admin_user, user_id, new_role)
    flash("Role updated." if ok else (error or "Could not update role."),
          "success" if ok else "error")
    return redirect(url_for("admin.users_page"))


@admin_bp.post("/requests/<int:request_id>/approve")
@login_required
def approve_request(request_id):
    admin_user = _require_admin()
    if admin_user is None:
        flash("You do not have permission to do that.", "error")
        return redirect(url_for("auth.profile"))

    ok, error = admin_service.approve_request(admin_user, request_id)
    flash("Registration approved." if ok else (error or "Could not approve request."),
          "success" if ok else "error")
    return redirect(url_for("admin.users_page"))


@admin_bp.post("/requests/<int:request_id>/reject")
@login_required
def reject_request(request_id):
    admin_user = _require_admin()
    if admin_user is None:
        flash("You do not have permission to do that.", "error")
        return redirect(url_for("auth.profile"))

    ok, error = admin_service.reject_request(admin_user, request_id)
    flash("Registration rejected." if ok else (error or "Could not reject request."),
          "success" if ok else "error")
    return redirect(url_for("admin.users_page"))
