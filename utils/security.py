"""CSRF protection.

A per-session token is generated on first use, embedded as a hidden field in
every POST form, and compared on every incoming POST. Comparison uses
`secrets.compare_digest` to avoid leaking information through timing.
"""

import secrets

from flask import session

CSRF_SESSION_KEY = "_csrf_token"
CSRF_FORM_FIELD = "csrf_token"


def generate_csrf_token() -> str:
    """Return the session's CSRF token, creating it on first use.

    Registered as a Jinja global so templates can call `csrf_token()`.
    """
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def rotate_csrf_token() -> str:
    """Issue a fresh token. Called on login and logout, when the session's
    privilege level changes."""
    session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)
    return session[CSRF_SESSION_KEY]


def validate_csrf_token(submitted: str | None) -> bool:
    expected = session.get(CSRF_SESSION_KEY)
    if not expected or not submitted:
        return False
    return secrets.compare_digest(expected, submitted)
