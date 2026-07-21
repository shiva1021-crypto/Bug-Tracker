"""Time-tracking business rules: logging work entries and updating an
issue's original/remaining estimate.

Logging time is open to any org member who can view the issue -- same
permission model comments use (Stage 6), since the spec doesn't restrict
who may log work. Updating the estimate is gated by
`issue_service.get_editor_permission()` (reused, not reimplemented) --
Admin/PM or the issue's own reporter, the same tier Stage 5 already
established for editing any other issue field.
"""

from repositories import issue_repository, time_entry_repository


def log_time(issue_id: int, user_id: int, hours_raw: str, description_raw: str) -> tuple[bool, str | None]:
    hours_raw = (hours_raw or "").strip()
    if not hours_raw:
        return False, "Enter the number of hours spent."

    try:
        hours = float(hours_raw)
    except ValueError:
        return False, "Hours must be a number."

    if hours <= 0:
        return False, "Hours must be greater than zero."

    description = (description_raw or "").strip() or None
    time_entry_repository.create(issue_id, user_id, hours, description)
    return True, None


def list_entries(issue_id: int, organization_id: int) -> list[dict]:
    return time_entry_repository.list_by_bug(issue_id, organization_id)


def total_spent(entries: list[dict]) -> float:
    """Always derived by summing the actual logged entries -- never a
    separately stored/cached total -- so it can never drift from what the
    entry list itself shows, per the Definition of Done."""
    return sum(float(entry["hours_spent"]) for entry in entries)


def update_estimate(
    issue_id: int, organization_id: int, estimate_raw: str, remaining_raw: str
) -> tuple[bool, str | None]:
    estimate = None
    estimate_raw = (estimate_raw or "").strip()
    if estimate_raw:
        try:
            estimate = float(estimate_raw)
        except ValueError:
            return False, "Estimate must be a number."
        if estimate < 0:
            return False, "Estimate cannot be negative."

    remaining = None
    remaining_raw = (remaining_raw or "").strip()
    if remaining_raw:
        try:
            remaining = float(remaining_raw)
        except ValueError:
            return False, "Remaining estimate must be a number."
        if remaining < 0:
            return False, "Remaining estimate cannot be negative."

    updated = issue_repository.update_estimate(issue_id, organization_id, estimate, remaining)
    if not updated:
        return False, "Could not update the estimate -- the issue may no longer exist."
    return True, None
