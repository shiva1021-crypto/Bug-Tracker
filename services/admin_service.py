"""Admin-panel business rules: user management and registration approval.

Every function here is organization-scoped and assumes the caller has
already established that the acting user is an admin of *that specific*
organization (see `verify_admin`). Nothing in this module trusts a
client-supplied organization id in isolation -- it always comes from a
freshly-fetched admin user row.
"""

from repositories import organization_repository, registration_request_repository, user_repository
from services import notification_service

ROLES = ["admin", "project_manager", "developer", "tester"]

ROLE_LABELS = {
    "admin": "Admin",
    "project_manager": "Project Manager",
    "developer": "Developer",
    "tester": "Tester",
}


def verify_admin(user_id: int) -> dict | None:
    """Return the caller's current user row if they are an admin, else None.

    This always re-reads the role from the database rather than trusting
    whatever role was written into the session at login time. That is a
    deliberate requirement from the spec: if an admin downgrades someone's
    role, the change must take effect on that person's very next request,
    not just at their next login. Session-cached role/org values are fine
    for cosmetic decisions (e.g. showing/hiding a sidebar link) but every
    admin-only route re-verifies through this function first.
    """
    user = user_repository.get_by_id(user_id)
    if user is None or user["role"] != "admin":
        return None
    return user


def list_users(organization_id: int) -> list[dict]:
    return user_repository.list_by_organization(organization_id)


def list_pending_requests(organization_id: int) -> list[dict]:
    return registration_request_repository.list_pending_by_organization(organization_id)


def change_role(admin_user: dict, target_user_id: int, new_role: str) -> tuple[bool, str | None]:
    """Change a user's role within the admin's own organization."""
    if new_role not in ROLES:
        return False, "That is not a valid role."

    target = user_repository.get_by_id_and_org(
        target_user_id, admin_user["organization_id"]
    )
    if target is None:
        # Either the id does not exist, or it belongs to another
        # organization -- both look identical to the caller, which is the
        # point: no information about other organizations leaks out.
        return False, "User not found in your organization."

    user_repository.update_role(target_user_id, admin_user["organization_id"], new_role)
    return True, None


def approve_request(admin_user: dict, request_id: int) -> tuple[bool, str | None]:
    """Approve a pending registration request, creating the real account."""
    req = registration_request_repository.get_by_id_and_org(
        request_id, admin_user["organization_id"]
    )
    if req is None or req["status"] != "pending":
        return False, "Request not found or already handled."

    if user_repository.email_exists(req["email"]):
        # The email was claimed by another account between the request being
        # filed and this approval (e.g. registered directly elsewhere).
        # Reject rather than create a duplicate/conflicting account.
        registration_request_repository.update_status(
            request_id, admin_user["organization_id"], "rejected"
        )
        return False, "An account with that email now exists elsewhere; request auto-rejected."

    user_repository.create(
        full_name=req["full_name"],
        email=req["email"],
        password_hash=req["password_hash"],
        organization_id=admin_user["organization_id"],
        role=req["requested_role"],
    )
    registration_request_repository.update_status(
        request_id, admin_user["organization_id"], "approved"
    )

    org = organization_repository.get_by_id(admin_user["organization_id"])
    notification_service.notify_registration_approved(
        req["email"], req["full_name"], org["name"] if org else ""
    )
    return True, None


def reject_request(admin_user: dict, request_id: int) -> tuple[bool, str | None]:
    """Reject a pending registration request. No account is created."""
    req = registration_request_repository.get_by_id_and_org(
        request_id, admin_user["organization_id"]
    )
    if req is None or req["status"] != "pending":
        return False, "Request not found or already handled."

    registration_request_repository.update_status(
        request_id, admin_user["organization_id"], "rejected"
    )

    org = organization_repository.get_by_id(admin_user["organization_id"])
    notification_service.notify_registration_rejected(
        req["email"], req["full_name"], org["name"] if org else ""
    )
    return True, None
