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

from services import auth_service, rate_limit_service
from utils.auth import current_user, end_session, login_required, start_session

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/")
def landing():
    """The public landing page.

    A logged-out visitor sees the marketing/hero page; a logged-in visitor
    is sent straight to their dashboard rather than seeing the hero page
    again. This replaced GET / 's old JSON app-status payload (moved to
    /api/status -- see routes/health_routes.py) so "/" could serve an
    actual page instead.
    """
    if current_user() is not None:
        return redirect(url_for("dashboard.dashboard"))
    return render_template("landing.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("auth/register.html")

    # Stage 10: rate limit registration attempts per IP -- keyed by IP only
    # (not the submitted email), since at this point the email may not
    # correspond to any real account yet and IP is what actually identifies
    # "one script hammering this endpoint."
    client_ip = request.remote_addr or "unknown"
    if rate_limit_service.is_blocked(client_ip):
        wait_seconds = rate_limit_service.seconds_until_reset(client_ip)
        flash(
            f"Too many registration attempts. Try again in about "
            f"{max(1, wait_seconds // 60)} minute(s).",
            "error",
        )
        return render_template("auth/register.html"), 429

    full_name = request.form.get("full_name", "")
    email = request.form.get("email", "")
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    organization_name = request.form.get("organization_name", "")

    errors = auth_service.validate_registration(
        full_name, email, password, confirm_password, organization_name
    )
    if errors:
        rate_limit_service.record_failure(client_ip)
        for error in errors:
            flash(error, "error")
        # Re-render with the non-secret fields preserved; never echo passwords.
        return (
            render_template(
                "auth/register.html",
                full_name=full_name,
                email=email,
                organization_name=organization_name,
            ),
            400,
        )

    rate_limit_service.record_success(client_ip)

    result = auth_service.register(
        full_name,
        email,
        password,
        organization_name,
        requester_ip=request.remote_addr,
    )

    if result["outcome"] == "created":
        start_session(result["user"])
        flash(
            f'Organization "{organization_name.strip()}" created. '
            "You're its admin.",
            "success",
        )
        return redirect(url_for("dashboard.dashboard"))

    # Existing organization: a registration_requests row was filed, no
    # account exists yet. Redirect (rather than render directly) so a page
    # refresh doesn't resubmit the registration form.
    return redirect(
        url_for("auth.registration_pending", organization=organization_name.strip())
    )


@auth_bp.get("/register/pending")
def registration_pending():
    """Shown right after filing a request to join an existing organization.

    Deliberately does not require login: no `users` row exists for this
    person yet (only a `registration_requests` row), so there is nothing to
    log them into. See STAGE-03-REPORT.md for why this reading was chosen.
    """
    organization_name = request.args.get("organization", "")
    return render_template("auth/pending.html", organization_name=organization_name)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    email = request.form.get("email", "")
    password = request.form.get("password", "")

    # Stage 10: rate limit both the IP and the account being targeted --
    # "per IP/account" per the spec -- so brute-forcing either one login
    # from many IPs, or many logins from one IP -- gets slowed down.
    # Blocked here means "don't even check the password," so a blocked
    # attacker can't use response timing to keep guessing.
    client_ip = request.remote_addr or "unknown"
    normalized_email = auth_service.normalize_email(email)
    if rate_limit_service.is_blocked(client_ip) or rate_limit_service.is_blocked(normalized_email):
        identifier = client_ip if rate_limit_service.is_blocked(client_ip) else normalized_email
        wait_seconds = rate_limit_service.seconds_until_reset(identifier)
        flash(
            f"Too many login attempts. Try again in about "
            f"{max(1, wait_seconds // 60)} minute(s).",
            "error",
        )
        return render_template("auth/login.html", email=email), 429

    user = auth_service.authenticate(email, password)
    if user is None:
        # Identical response for unknown email, wrong password and an email
        # that only exists as a still-pending registration request.
        rate_limit_service.record_failure(client_ip)
        if normalized_email:
            rate_limit_service.record_failure(normalized_email)
        flash(auth_service.GENERIC_LOGIN_ERROR, "error")
        return render_template("auth/login.html", email=email), 401

    rate_limit_service.record_success(client_ip)
    rate_limit_service.record_success(normalized_email)
    start_session(user)
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.post("/logout")
def logout():
    """POST only -- a GET link could be triggered cross-site to force logout."""
    end_session()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.get("/profile")
@login_required
def profile():
    session_user = current_user()
    page_data = auth_service.get_profile_page_data(
        session_user["id"], session_user["organization_id"]
    )
    if page_data is None:
        # Session points at a user that no longer exists.
        end_session()
        flash("Please log in to continue.", "error")
        return redirect(url_for("auth.login"))
    return render_template(
        "profile.html",
        current_user_id=session_user["id"],
        can_view_email=True,
        **page_data,
    )
