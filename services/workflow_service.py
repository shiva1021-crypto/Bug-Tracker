"""Workflow business rules: status transitions, assignment, comments,
history, and watchers.

Kept in its own module rather than folded into `issue_service` because it
is a distinct concern (Stage 6) layered on top of the issue CRUD Stage 5
already built -- issue_service.py is left untouched except for the two
history-recording calls the spec requires on create/edit (see its
docstring), and the DEFAULT_STATUS change.
"""

from repositories import (
    bug_history_repository,
    comment_repository,
    issue_repository,
    user_repository,
    watcher_repository,
)

# Canonical order from the spec. Kept as an ordered list (not a set) since
# the frontend needs to render them in order; nothing in this module
# actually enforces sequential-only movement between them -- see
# STAGE-06-REPORT.md for why (the spec deliberately keeps `bugs.status` a
# VARCHAR rather than an ENUM "for future custom workflows", and neither the
# feature list nor the Definition of Done requires rejecting a jump, e.g.
# Idea -> Done -- only the assignment-driven To Do -> In Progress
# auto-transition is a hard rule). Any permitted user may move a permitted
# issue to any of the five statuses.
STATUSES = ["Idea", "To Do", "In Progress", "Testing", "Done"]

# Same two roles as issue_service.CAN_EDIT_ANY_ROLES, but defined locally --
# this module's permission rules are conceptually separate from "who can
# edit issue fields" even though the role set happens to match today, and
# every other service module in this codebase defines its own role-set
# constant rather than cross-importing one.
ADMIN_OR_PM_ROLES = {"admin", "project_manager"}


def can_update_status(user_id: int, issue: dict) -> dict | None:
    """Fresh DB check, same pattern as issue_service.get_editor_permission:
    the user row if they may change this issue's status, else None.

    Per the spec's reusable rule: true if Admin/PM, OR a Developer who is
    the assigned user on this issue. Testers, and Developers not assigned
    to this issue, are never allowed -- re-reading the role from the
    database on every call is what makes the Definition of Done's "a Tester
    cannot move status via the API even by crafting the request" item hold,
    since nothing here trusts a client-supplied role.
    """
    user = user_repository.get_by_id(user_id)
    if user is None:
        return None
    if user["role"] in ADMIN_OR_PM_ROLES:
        return user
    if user["role"] == "developer" and issue["assigned_to"] == user["id"]:
        return user
    return None


def can_assign(user_id: int) -> dict | None:
    """Fresh DB check: the user row if they may assign/reassign issues
    (Admin/PM only, per the spec), else None."""
    user = user_repository.get_by_id(user_id)
    if user is None:
        return None
    if user["role"] in ADMIN_OR_PM_ROLES:
        return user
    return None


def list_assignable_developers(organization_id: int) -> list[dict]:
    """Developers in the org, for the assignment dropdown -- the spec's
    frontend section calls for "developers in the project's organization",
    not the wider set of every role."""
    users = user_repository.list_by_organization(organization_id)
    return [user for user in users if user["role"] == "developer"]


def change_status(issue: dict, new_status: str, changed_by_user: dict) -> tuple[bool, str | None]:
    """Change an issue's status. Assumes `can_update_status` has already
    been checked by the caller (route) -- re-validated here defensively so
    this function is never safe to call without that guard having passed.
    """
    if new_status not in STATUSES:
        return False, "Select a valid status."

    old_status = issue["status"]
    if new_status == old_status:
        return True, None  # no-op; nothing to persist or record

    updated = issue_repository.update_status(issue["id"], issue["organization_id"], new_status)
    if not updated:
        return False, "Could not update status -- the issue may no longer exist."

    bug_history_repository.record(
        bug_id=issue["id"],
        changed_by=changed_by_user["id"],
        old_status=old_status,
        new_status=new_status,
    )
    return True, None


def assign_issue(
    issue: dict, new_assigned_to_raw: str, changed_by_user: dict, organization_id: int
) -> tuple[bool, str | None]:
    """Assign or unassign an issue. Assumes `can_assign` has already been
    checked by the caller.

    Applies the auto-transition rule ("assigning ... auto-transitions it
    from 'To Do' to 'In Progress' (if it was in 'To Do')") and records it as
    a *second*, separate history row alongside the assignment change --
    since the spec's history examples list "X assigned to Y" and "X changed
    status from Y to Z" as distinct sentence shapes, a combined event is
    recorded as one of each rather than inventing a third combined
    sentence.
    """
    new_assigned_to_raw = (new_assigned_to_raw or "").strip()
    new_assigned_to: int | None = None

    if new_assigned_to_raw:
        try:
            new_assigned_to = int(new_assigned_to_raw)
        except ValueError:
            return False, "Invalid assignee selection."

        assignee = user_repository.get_by_id_and_org(new_assigned_to, organization_id)
        if assignee is None or assignee["role"] != "developer":
            return False, "Assignee must be a developer in your organization."

    old_assigned_to = issue["assigned_to"]
    if new_assigned_to == old_assigned_to:
        return True, None  # no-op

    old_status = issue["status"]
    new_status = old_status
    if new_assigned_to is not None and old_status == "To Do":
        new_status = "In Progress"

    updated = issue_repository.update_assignment(
        issue["id"], organization_id, new_assigned_to, new_status
    )
    if not updated:
        return False, "Could not update assignment -- the issue may no longer exist."

    bug_history_repository.record(
        bug_id=issue["id"],
        changed_by=changed_by_user["id"],
        old_assigned_to=old_assigned_to,
        new_assigned_to=new_assigned_to,
    )
    if new_status != old_status:
        bug_history_repository.record(
            bug_id=issue["id"],
            changed_by=changed_by_user["id"],
            old_status=old_status,
            new_status=new_status,
        )
    return True, None


def add_comment(issue_id: int, user_id: int, text: str) -> tuple[bool, str | None]:
    text = (text or "").strip()
    if not text:
        return False, "Comment cannot be empty."
    comment_repository.create(issue_id, user_id, text)
    return True, None


def list_comments(issue_id: int, organization_id: int) -> list[dict]:
    return comment_repository.list_by_bug(issue_id, organization_id)


def list_history(issue_id: int, organization_id: int) -> list[dict]:
    return bug_history_repository.list_by_bug(issue_id, organization_id)


def toggle_watch(issue_id: int, user_id: int) -> bool:
    """Flip the current user's watch state on this issue. Returns the new
    state (True = now watching)."""
    if watcher_repository.is_watching(issue_id, user_id):
        watcher_repository.remove(issue_id, user_id)
        return False
    watcher_repository.add(issue_id, user_id)
    return True


def is_watching(issue_id: int, user_id: int) -> bool:
    return watcher_repository.is_watching(issue_id, user_id)


def watcher_count(issue_id: int) -> int:
    return watcher_repository.count(issue_id)
