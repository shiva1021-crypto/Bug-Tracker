"""Authentication and registration business rules.

Passwords are hashed with Werkzeug's `generate_password_hash` (scrypt by
default) before they ever reach the repository layer. Plaintext passwords are
never stored, logged, or returned.

Stage 3 adds the organization/role decision that happens at registration:
a brand-new organization name makes the registrant that org's first user,
automatically Admin; an existing organization name creates a pending
`registration_requests` row instead of a `users` row and an admin of that
org must approve or reject it later (see `services/admin_service.py`).

Stage 4 adds one more step to the new-organization path: a "General"
project is auto-created immediately, per that stage's Definition of Done
("A brand-new organization has exactly one project ('General') immediately
after registration.") -- see `services/project_service.py`.
"""

import re

from werkzeug.security import check_password_hash, generate_password_hash

from repositories import (
    comment_repository,
    issue_repository,
    organization_repository,
    registration_request_repository,
    user_repository,
)
from services import dashboard_service, project_service

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MIN_PASSWORD_LENGTH = 8
MAX_NAME_LENGTH = 150
MAX_EMAIL_LENGTH = 150
MAX_ORG_NAME_LENGTH = 150

# The role assigned to a pending request when nothing else was specified.
# The register form does not ask a joining user to pick a role (the spec's
# frontend section does not list one), so new requests land at the lowest
# privilege role and an admin assigns something more specific on approval.
DEFAULT_REQUESTED_ROLE = "tester"

# Shown for every failed login, whether the email is unknown or the password is
# wrong. Never reveal which one it was.
GENERIC_LOGIN_ERROR = "Invalid email or password."


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_registration(
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
    organization_name: str,
) -> list[str]:
    """Server-side validation for registration. Returns a list of errors.

    The register page also checks the password match in JavaScript, but that is
    a convenience only -- this function is the authority and re-checks everything.
    """
    errors: list[str] = []

    full_name = (full_name or "").strip()
    email = normalize_email(email)
    organization_name = (organization_name or "").strip()

    if not organization_name:
        errors.append("Organization name is required.")
    elif len(organization_name) > MAX_ORG_NAME_LENGTH:
        errors.append(
            f"Organization name must be {MAX_ORG_NAME_LENGTH} characters or fewer."
        )

    if not full_name:
        errors.append("Full name is required.")
    elif len(full_name) > MAX_NAME_LENGTH:
        errors.append(f"Full name must be {MAX_NAME_LENGTH} characters or fewer.")

    if not email:
        errors.append("Email is required.")
    elif len(email) > MAX_EMAIL_LENGTH:
        errors.append(f"Email must be {MAX_EMAIL_LENGTH} characters or fewer.")
    elif not EMAIL_PATTERN.match(email):
        errors.append("Enter a valid email address.")

    if not password:
        errors.append("Password is required.")
    elif len(password) < MIN_PASSWORD_LENGTH:
        errors.append(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )

    if password != confirm_password:
        errors.append("Passwords do not match.")

    # Only hit the database if the email itself is well-formed.
    if email and not errors:
        if user_repository.email_exists(email):
            errors.append("An account with that email already exists.")
        elif registration_request_repository.pending_email_exists(email):
            errors.append(
                "A registration request for that email is already pending approval."
            )

    return errors


def register(
    full_name: str,
    email: str,
    password: str,
    organization_name: str,
    requester_ip: str | None,
) -> dict:
    """Create an account or a pending request, depending on the org name.

    Assumes `validate_registration` has already passed. Returns:
      {"outcome": "created", "user": {...}}   -- new org, registrant is Admin
      {"outcome": "pending"}                  -- existing org, awaiting approval
    """
    full_name = (full_name or "").strip()
    email = normalize_email(email)
    organization_name = (organization_name or "").strip()
    password_hash = generate_password_hash(password)

    org = organization_repository.get_by_name(organization_name)

    if org is None:
        organization_id = organization_repository.create(organization_name)
        user_id = user_repository.create(
            full_name=full_name,
            email=email,
            password_hash=password_hash,
            organization_id=organization_id,
            role="admin",
        )
        project_service.create_default_project(organization_id)
        # Stage 10: seed this brand-new organization's default dashboard
        # layout now, the same moment its default project is created --
        # so "a new user's dashboard shows the default widget set with no
        # manual setup" holds for the very first user too, not just
        # members who join later.
        dashboard_service.ensure_org_defaults(organization_id)
        return {
            "outcome": "created",
            "user": {
                "id": user_id,
                "full_name": full_name,
                "email": email,
                "organization_id": organization_id,
                "role": "admin",
            },
        }

    registration_request_repository.create(
        organization_id=org["id"],
        full_name=full_name,
        email=email,
        password_hash=password_hash,
        requested_role=DEFAULT_REQUESTED_ROLE,
        requester_ip=requester_ip,
    )
    return {"outcome": "pending"}


def authenticate(email: str, password: str) -> dict | None:
    """Return the user dict on success, None on any failure.

    A single None result covers both "no such email" and "wrong password" so the
    route layer cannot accidentally leak which one occurred. It also covers a
    third case that did not exist before Stage 3: an email that only exists in
    `registration_requests` (a pending signup with no `users` row yet) looks
    exactly like an unknown email here -- there is deliberately no special
    "your request is still pending" message on the login form, because that
    would leak account-existence information the same way a distinct
    wrong-password message would.
    """
    user = user_repository.get_by_email(normalize_email(email))
    if user is None:
        return None
    if not check_password_hash(user["password_hash"], password or ""):
        return None
    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "organization_id": user["organization_id"],
        "role": user["role"],
    }


def get_profile(user_id: int) -> dict | None:
    """Fetch the display data for the profile page."""
    return user_repository.get_by_id(user_id)


def get_profile_page_data(user_id: int, organization_id: int) -> dict | None:
    """Everything the reference-ui profile.html layout needs: the user row,
    the stat-card counts, a handful of recently reported/assigned issues,
    and recent comments. The page itself is Stage 2 scope, but its reference
    layout assumes issue/comment data that only exists once later stages
    are built -- which they now are, so this pulls it for real rather than
    leaving those sections empty."""
    user = user_repository.get_by_id(user_id)
    if user is None:
        return None
    stats = issue_repository.profile_counts(user_id, organization_id)
    stats["comment_count"] = comment_repository.count_by_user(user_id, organization_id)
    return {
        "user": user,
        "stats": stats,
        "reported_bugs": issue_repository.list_reported_by_user(user_id, organization_id),
        "assigned_bugs": issue_repository.list_assigned_by_user(user_id, organization_id),
        "recent_comments": comment_repository.list_recent_by_user(user_id, organization_id),
    }
