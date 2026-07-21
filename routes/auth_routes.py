"""HTTP handlers for registration, login, logout and profile.

Thin layer: read the form, delegate to `auth_service`, render or redirect.
CSRF validation happens globally in `app.py` before these run.
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from services import auth_service
from utils.auth import current_user, end_session, login_required, start_session

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("auth/register.html")

    full_name = request.form.get("full_name", "")
    email = request.form.get("email", "")
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    errors = auth_service.validate_registration(
        full_name, email, password, confirm_password
    )
    if errors:
        for error in errors:
            flash(error, "error")
        # Re-render with the non-secret fields preserved; never echo passwords.
        return (
            render_template(
                "auth/register.html", full_name=full_name, email=email
            ),
            400,
        )

    auth_service.register(full_name, email, password)
    flash("Account created. Please log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    email = request.form.get("email", "")
    password = request.form.get("password", "")

    user = auth_service.authenticate(email, password)
    if user is None:
        # Identical response for unknown email and wrong password.
        flash(auth_service.GENERIC_LOGIN_ERROR, "error")
        return render_template("auth/login.html", email=email), 401

    start_session(user)
    return redirect(url_for("auth.profile"))


@auth_bp.post("/logout")
def logout():
    """POST only — a GET link could be triggered cross-site to force logout."""
    end_session()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.get("/profile")
@login_required
def profile():
    user = auth_service.get_profile(current_user()["id"])
    if user is None:
        # Session points at a user that no longer exists.
        end_session()
        flash("Please log in to continue.", "error")
        return redirect(url_for("auth.login"))
    return render_template("profile.html", user=user)
