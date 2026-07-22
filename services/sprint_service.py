"""Sprint business rules: validation, lifecycle (future -> active -> closed),
and moving issues between the backlog and a sprint.

Creating, starting and closing a sprint are gated the same way project
creation is: the Stage 3 permission matrix grants "Manage sprints" to
Admin/PM only (see `services/project_service.py`'s own docstring, which
names this exact permission) and Stage 8 is the first stage that
actually has sprints to manage. `verify_sprint_manager()` follows the
same fresh-DB-read pattern as every other permission check in this
codebase (`admin_service.verify_admin`, `project_service.verify_project_creator`,
`workflow_service.can_assign`) -- never trusts the session's cached role.
"""

from datetime import datetime

from repositories import issue_repository, sprint_repository, user_repository

CAN_MANAGE_SPRINTS_ROLES = {"admin", "project_manager"}

MAX_NAME_LENGTH = 120

# Sprints shown on the backlog page -- closed sprints have their own
# implicit "done" state and aren't part of active planning anymore, so
# they're deliberately left off (see STAGE-08-REPORT.md for why this
# doesn't need a "closed sprints" archive view -- out of scope this stage).
OPEN_STATUSES = ["active", "future"]


def verify_sprint_manager(user_id: int) -> dict | None:
    """Fresh DB check: the user row if they may create/start/close
    sprints or move issues between the backlog and a sprint, else None."""
    user = user_repository.get_by_id(user_id)
    if user is None or user["role"] not in CAN_MANAGE_SPRINTS_ROLES:
        return None
    return user


def validate_sprint(
    name: str, goal_raw: str, start_date_raw: str, end_date_raw: str
) -> tuple[list[str], dict]:
    errors: list[str] = []

    name = (name or "").strip()
    if not name:
        errors.append("Sprint name is required.")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"Sprint name must be {MAX_NAME_LENGTH} characters or fewer.")

    goal = (goal_raw or "").strip() or None

    start_date = None
    start_date_raw = (start_date_raw or "").strip()
    if start_date_raw:
        try:
            start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Enter a valid start date.")

    end_date = None
    end_date_raw = (end_date_raw or "").strip()
    if end_date_raw:
        try:
            end_date = datetime.strptime(end_date_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Enter a valid end date.")

    if start_date and end_date and end_date < start_date:
        errors.append("End date must be on or after the start date.")

    cleaned = {"name": name, "goal": goal, "start_date": start_date, "end_date": end_date}
    return errors, cleaned


def create_sprint(organization_id: int, project_id: int, cleaned: dict) -> int:
    return sprint_repository.create(
        organization_id=organization_id,
        project_id=project_id,
        name=cleaned["name"],
        goal=cleaned["goal"],
        start_date=cleaned["start_date"],
        end_date=cleaned["end_date"],
    )


def get_sprint(sprint_id: int, organization_id: int) -> dict | None:
    return sprint_repository.get_by_id_and_org(sprint_id, organization_id)


def list_open_sprints(organization_id: int, project_id: int) -> list[dict]:
    """Future and active sprints for one project, active sprint(s) first
    (there is at most one, but this doesn't assume that while sorting),
    then future sprints in creation order -- the order the backlog page
    renders its sprint sections in."""
    sprints = sprint_repository.list_by_project(project_id, organization_id, OPEN_STATUSES)
    return sorted(sprints, key=lambda s: (0 if s["status"] == "active" else 1, s["created_at"]))


def start_sprint(sprint: dict, manager_user: dict) -> tuple[bool, str | None]:
    """Move a sprint from `future` to `active`. Assumes `verify_sprint_manager`
    has already been checked by the caller."""
    if sprint["status"] != "future":
        return False, "Only a sprint that hasn't started yet can be started."

    active = sprint_repository.get_active_for_project(sprint["project_id"], sprint["organization_id"])
    if active is not None:
        return False, (
            f'Sprint "{active["name"]}" is already active in this project -- '
            "close it before starting another."
        )

    updated = sprint_repository.set_status(sprint["id"], sprint["organization_id"], "active")
    if not updated:
        return False, "Could not start the sprint -- it may no longer exist."
    return True, None


def close_sprint(sprint: dict, manager_user: dict) -> tuple[bool, str | None]:
    """Move a sprint from `active` to `closed`. Assumes `verify_sprint_manager`
    has already been checked by the caller."""
    if sprint["status"] != "active":
        return False, "Only the active sprint can be closed."

    updated = sprint_repository.set_status(sprint["id"], sprint["organization_id"], "closed")
    if not updated:
        return False, "Could not close the sprint -- it may no longer exist."
    return True, None


def assign_issue_to_sprint(
    issue: dict, sprint_id_raw: str, organization_id: int
) -> tuple[bool, str | None]:
    """Move an issue into a sprint, or back to the backlog if
    `sprint_id_raw` is empty. Assumes `verify_sprint_manager` has already
    been checked by the caller."""
    sprint_id_raw = (sprint_id_raw or "").strip()

    if not sprint_id_raw:
        updated = issue_repository.update_sprint(issue["id"], organization_id, None)
        if not updated:
            return False, "Could not move the issue to the backlog."
        return True, None

    try:
        sprint_id = int(sprint_id_raw)
    except ValueError:
        return False, "Invalid sprint selection."

    sprint = sprint_repository.get_by_id_and_org(sprint_id, organization_id)
    if sprint is None:
        return False, "Sprint not found."
    if sprint["project_id"] != issue["project_id"]:
        return False, "A sprint can only contain issues from its own project."
    if sprint["status"] == "closed":
        return False, "Cannot add issues to a closed sprint."

    updated = issue_repository.update_sprint(issue["id"], organization_id, sprint_id)
    if not updated:
        return False, "Could not move the issue into that sprint."
    return True, None


def list_backlog(organization_id: int, project_id: int) -> list[dict]:
    return issue_repository.list_backlog_issues(organization_id, project_id)


def list_sprint_issues(sprint_id: int, organization_id: int) -> list[dict]:
    return issue_repository.list_by_sprint(sprint_id, organization_id)


def total_story_points(issues: list[dict]) -> int:
    """Sum of `story_points`, treating an unset value as 0 -- the same
    minimal reading `board_service`/the burndown chart use, since
    `story_points` has been an optional field since Stage 5."""
    return sum(issue["story_points"] or 0 for issue in issues)
