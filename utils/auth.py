"""Session helpers and the `login_required` gate.

Session contents: `user_id`, `full_name`, `organization_id`, and `role`.
`organization_id` and `role` were added in Stage 3 -- they are a *cached
snapshot* taken at login time, convenient for cosmetic decisions like which
sidebar links to show. They are not re-verified on every request, so they
can go stale the moment an admin changes someone's role. Anything that
actually gates a sensitive action (the admin panel, and every role check
added in later stages) must re-read the role from the database instead of
trusting this snapshot -- see `services/admin_service.py::verify_admin`.
"""

from functools import wraps

from flask import flash, redirect, session, url_for

from utils.security import rotate_csrf_token

SESSION_USER_ID = "user_id"
SESSION_FULL_NAME = "full_name"
SESSION_ORG_ID = "organization_id"
SESSION_ROLE = "role"


def start_session(user: dict) -> None:
    """Log a user in.

    The session is cleared first so no state from the logged-out session
    survives, and the CSRF token is rotated because the privilege level changed
    (defends against session-fixation style attacks).
    """
    session.clear()
    session[SESSION_USER_ID] = user["id"]
    session[SESSION_FULL_NAME] = user["full_name"]
    session[SESSION_ORG_ID] = user["organization_id"]
    session[SESSION_ROLE] = user["role"]
    session.permanent = True
    rotate_csrf_token()


def end_session() -> None:
    """Log the user out and issue a fresh CSRF token for the anonymous session."""
    session.clear()
    rotate_csrf_token()


def is_logged_in() -> bool:
    return SESSION_USER_ID in session


def current_user() -> dict | None:
    """Lightweight view of the logged-in user, straight from the session.

    Returns None when logged out. Injected into every template as
    `current_user`. `organization_id` and `role` here are the snapshot from
    login -- fine for display, not authoritative for permission checks.
    """
    if not is_logged_in():
        return None
    return {
        "id": session[SESSION_USER_ID],
        "full_name": session.get(SESSION_FULL_NAME),
        "organization_id": session.get(SESSION_ORG_ID),
        "role": session.get(SESSION_ROLE),
    }


def login_required(view):
    """Redirect to the login page if there is no logged-in user."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_logged_in():
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped
