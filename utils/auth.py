"""Session helpers and the `login_required` gate.

Session contents established in this stage: `user_id` and `full_name`.
(`organization_id` and `role` arrive in a later stage.)
"""

from functools import wraps

from flask import flash, redirect, session, url_for

from utils.security import rotate_csrf_token

SESSION_USER_ID = "user_id"
SESSION_FULL_NAME = "full_name"


def start_session(user: dict) -> None:
    """Log a user in.

    The session is cleared first so no state from the logged-out session
    survives, and the CSRF token is rotated because the privilege level changed
    (defends against session-fixation style attacks).
    """
    session.clear()
    session[SESSION_USER_ID] = user["id"]
    session[SESSION_FULL_NAME] = user["full_name"]
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

    Returns None when logged out. Injected into every template as `current_user`.
    """
    if not is_logged_in():
        return None
    return {
        "id": session[SESSION_USER_ID],
        "full_name": session.get(SESSION_FULL_NAME),
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
