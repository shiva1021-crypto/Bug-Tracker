"""Issue business rules: hierarchy validation, field validation, screenshot
handling, permission checks and create/update orchestration.

Anyone in an organization may create an issue -- the Stage 3 permission
matrix grants "Create issues" to all four roles, so there is no creator
role gate here (unlike projects, which are Admin/PM only). Editing is
different: `get_editor_permission()` re-reads the caller's role from the
database, the same fresh-check pattern used everywhere else a permission
matters (`admin_service.verify_admin`, `project_service.verify_project_creator`).
"""

import io
import re
import secrets
from datetime import date, datetime

from PIL import Image, UnidentifiedImageError

from config import config
from repositories import (
    bug_history_repository,
    issue_repository,
    project_repository,
    user_repository,
    version_repository,
)

ISSUE_TYPES = ["Epic", "Story", "Task", "Bug", "Subtask"]

# Hierarchy rule from the spec: "an Epic can contain Stories and Tasks. A
# Story can contain Subtasks. Task and Bug are flat... except Bug/Task
# themselves can't be parents."
ALLOWED_CHILDREN = {
    "Epic": {"Story", "Task"},
    "Story": {"Subtask"},
    "Task": set(),
    "Bug": set(),
    "Subtask": set(),
}

# The inverse of ALLOWED_CHILDREN: for a given child type, which parent
# types are legal. Computed once so the create/edit forms and their
# client-side JS filter (see static/script.js::initParentFilter, which
# must be kept in sync with this) agree with the server's own rule.
VALID_PARENT_TYPES_FOR_CHILD = {
    child_type: [
        parent_type
        for parent_type, child_types in ALLOWED_CHILDREN.items()
        if child_type in child_types
    ]
    for child_type in ISSUE_TYPES
}

PRIORITIES = ["Low", "Medium", "High", "Critical"]
DEFAULT_PRIORITY = "Medium"

SEVERITIES = ["Minor", "Major", "Critical", "Blocker"]
DEFAULT_SEVERITY = "Minor"

DEFAULT_CATEGORY = "General"
DEFAULT_STATUS = "Idea"

MAX_TITLE_LENGTH = 255
MAX_CATEGORY_LENGTH = 80
MAX_LABELS_LENGTH = 255

# Only Admins and Project Managers may edit any issue; a Developer/Tester
# may only edit an issue they personally reported. Per the Stage 3
# permission matrix: "Edit any issue: Admin/PM (yes), Developer/Tester
# (own reports only)."
CAN_EDIT_ANY_ROLES = {"admin", "project_manager"}

# --- Screenshot upload rules -------------------------------------------
#
# The spec requires validating both the file extension AND the actual file
# content (so a renamed executable can't pass as a ".png"), limiting size,
# and storing outside anything web-servable with a random filename.
#
# Python 3.13 removed the old `imghdr` module, so Pillow is used instead --
# opening the bytes and asking Pillow what format it actually recognizes is
# a stronger check than `imghdr` ever was anyway, since Pillow has to fully
# understand the format to open it at all.
MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024  # 5 MB

ALLOWED_SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# Pillow's `Image.format` value -> the extension we store it under. This is
# the extension actually used on disk; it comes from what Pillow detected,
# never from the filename the browser sent.
ALLOWED_SCREENSHOT_FORMATS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "GIF": ".gif",
    "WEBP": ".webp",
}


def get_issue(issue_id: int, organization_id: int) -> dict | None:
    return issue_repository.get_detail_by_id_and_org(issue_id, organization_id)


def list_children(issue_id: int, organization_id: int) -> list[dict]:
    return issue_repository.list_children(issue_id, organization_id)


def list_by_project(project_id: int, organization_id: int) -> list[dict]:
    return issue_repository.list_by_project(project_id, organization_id)


def list_org_users(organization_id: int) -> list[dict]:
    """Every member of one organization -- used by the Stage 8 issue list
    page to populate its "Assignee" filter dropdown with real org members,
    not just the developers Stage 6's assignment control restricts to
    (a filter should be able to find issues currently assigned to anyone,
    including a user whose role has since changed)."""
    return user_repository.list_by_organization(organization_id)


def list_potential_parents(organization_id: int, exclude_issue_id: int | None = None) -> list[dict]:
    """Light-weight issue list for the Add-issue page's client-side filter.

    Includes every issue in the org; the browser narrows this down to the
    chosen project + the types `VALID_PARENT_TYPES_FOR_CHILD` allows for
    the chosen issue type, as those two fields change. Excluding
    `exclude_issue_id` matters on the edit page, so an issue never appears
    as a candidate parent for itself.
    """
    issues = issue_repository.list_by_organization(organization_id)
    if exclude_issue_id is None:
        return issues
    return [issue for issue in issues if issue["id"] != exclude_issue_id]


def list_valid_parents_for(
    organization_id: int,
    project_id: int,
    child_issue_type: str,
    exclude_issue_id: int | None = None,
) -> list[dict]:
    """Server-side pre-filtered parent candidates for the Edit page.

    Unlike the Add page, an issue's project and type never change once
    created (see `validate_issue`'s docstring), so there is nothing for
    client-side JS to react to -- the correct list can just be computed
    once, here, at render time.
    """
    allowed_parent_types = set(VALID_PARENT_TYPES_FOR_CHILD.get(child_issue_type, []))
    if not allowed_parent_types:
        return []
    candidates = list_potential_parents(organization_id, exclude_issue_id=exclude_issue_id)
    return [
        issue
        for issue in candidates
        if issue["project_id"] == project_id and issue["issue_type"] in allowed_parent_types
    ]


def get_editor_permission(user_id: int, issue: dict) -> dict | None:
    """Fresh DB check: the user row if they may edit this issue, else None.

    Re-reads the role from the database (never trusts the session's
    cached role) so a role change or reassignment takes effect on the very
    next request, matching the pattern established for admin actions and
    project creation.
    """
    user = user_repository.get_by_id(user_id)
    if user is None:
        return None
    if user["role"] in CAN_EDIT_ANY_ROLES or issue["reporter_id"] == user["id"]:
        return user
    return None


def _get_ancestor_chain_ids(start_id: int, organization_id: int, max_depth: int = 50) -> list[int]:
    """Walk upward from `start_id` via parent_id, returning every id seen
    (including `start_id` itself). Used to detect cycles: if the issue
    being created/edited appears in its *chosen parent's* ancestor chain,
    setting that parent would create a loop. `max_depth` is a defensive cap
    only -- the hierarchy rule (max 2 levels) means real chains are short;
    it exists so a data inconsistency can never hang a request.
    """
    ids: list[int] = []
    current_id: int | None = start_id
    depth = 0
    while current_id is not None and depth < max_depth:
        ids.append(current_id)
        row = issue_repository.get_by_id_and_org(current_id, organization_id)
        if row is None:
            break
        current_id = row["parent_id"]
        depth += 1
    return ids


def validate_issue(
    organization_id: int,
    project_id: int,
    issue_type: str,
    parent_id_raw: str,
    title: str,
    description: str,
    reproduction_steps: str,
    category: str,
    priority: str,
    severity: str,
    labels_raw: str,
    story_points_raw: str,
    due_date_raw: str,
    fix_version_raw: str = "",
    current_issue_id: int | None = None,
) -> tuple[list[str], dict]:
    """Server-side validation for creating or editing an issue.

    `project_id` and `issue_type` are always supplied by the *route*, never
    read from the edit form -- see the module docstring and
    `routes/issue_routes.py::edit_issue` for why they are fixed after
    creation. Returns `(errors, cleaned)`; `cleaned` only has meaningful
    values when `errors` is empty.

    Hierarchy validation (parent type/project/cycle) is implemented here,
    as a single reusable function, per the spec's explicit instruction not
    to inline it in the route.
    """
    errors: list[str] = []

    project = project_repository.get_by_id_and_org(project_id, organization_id)
    if project is None:
        errors.append("Select a valid project.")

    if issue_type not in ISSUE_TYPES:
        errors.append("Select a valid issue type.")

    title = (title or "").strip()
    if not title:
        errors.append("Title is required.")
    elif len(title) > MAX_TITLE_LENGTH:
        errors.append(f"Title must be {MAX_TITLE_LENGTH} characters or fewer.")

    description = (description or "").strip()
    if not description:
        errors.append("Description is required.")

    reproduction_steps = (reproduction_steps or "").strip() or None

    category = (category or "").strip() or DEFAULT_CATEGORY
    if len(category) > MAX_CATEGORY_LENGTH:
        errors.append(f"Category must be {MAX_CATEGORY_LENGTH} characters or fewer.")

    if priority not in PRIORITIES:
        errors.append("Select a valid priority.")

    if severity not in SEVERITIES:
        errors.append("Select a valid severity.")

    # --- parent -----------------------------------------------------
    parent_id: int | None = None
    parent_id_raw = (parent_id_raw or "").strip()
    if parent_id_raw:
        try:
            parent_id = int(parent_id_raw)
        except ValueError:
            errors.append("Invalid parent selection.")
            parent_id = None

        if parent_id is not None:
            parent = issue_repository.get_by_id_and_org(parent_id, organization_id)
            if parent is None:
                errors.append("Selected parent issue was not found in your organization.")
            elif project is not None and parent["project_id"] != project["id"]:
                errors.append("Parent must belong to the same project.")
            elif issue_type in ISSUE_TYPES:
                allowed_parent_types = VALID_PARENT_TYPES_FOR_CHILD.get(issue_type, [])
                if parent["issue_type"] not in allowed_parent_types:
                    errors.append(
                        f'A {issue_type} cannot have a {parent["issue_type"]} as its parent.'
                    )
                elif current_issue_id is not None:
                    ancestor_ids = _get_ancestor_chain_ids(parent_id, organization_id)
                    if current_issue_id in ancestor_ids:
                        errors.append(
                            "That parent would create a circular chain of issues."
                        )

    # --- labels -------------------------------------------------------
    raw_labels = [label.strip() for label in (labels_raw or "").split(",")]
    labels = ", ".join(label for label in raw_labels if label) or None
    if labels and len(labels) > MAX_LABELS_LENGTH:
        errors.append(f"Labels must be {MAX_LABELS_LENGTH} characters or fewer combined.")

    # --- story points ---------------------------------------------------
    story_points: int | None = None
    story_points_raw = (story_points_raw or "").strip()
    if story_points_raw:
        try:
            story_points = int(story_points_raw)
            if story_points < 0:
                raise ValueError
        except ValueError:
            errors.append("Story points must be a whole, non-negative number.")
            story_points = None

    # --- due date -----------------------------------------------------
    due_date: date | None = None
    due_date_raw = (due_date_raw or "").strip()
    if due_date_raw:
        try:
            due_date = datetime.strptime(due_date_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Enter a valid due date.")

    # --- fix version (Stage 9) -----------------------------------------
    fix_version_id: int | None = None
    fix_version_raw = (fix_version_raw or "").strip()
    if fix_version_raw:
        try:
            fix_version_id = int(fix_version_raw)
        except ValueError:
            errors.append("Invalid fix version selection.")
            fix_version_id = None

        if fix_version_id is not None:
            version = version_repository.get_by_id_and_org(fix_version_id, organization_id)
            if version is None:
                errors.append("Selected fix version was not found in your organization.")
            elif project is not None and version["project_id"] != project["id"]:
                errors.append("Fix version must belong to the same project as the issue.")

    cleaned = {
        "project_id": project["id"] if project else None,
        "issue_type": issue_type,
        "parent_id": parent_id,
        "title": title,
        "description": description,
        "reproduction_steps": reproduction_steps,
        "category": category,
        "priority": priority,
        "severity": severity,
        "labels": labels,
        "story_points": story_points,
        "due_date": due_date,
        "fix_version_id": fix_version_id,
    }
    return errors, cleaned


def validate_and_store_screenshot(file_storage) -> tuple[str | None, str | None]:
    """Validate an uploaded screenshot and store it. Returns
    `(stored_filename, error)`.

    `stored_filename` is None (with no error) when no file was submitted --
    the screenshot is optional. It is also None (with an error set) if
    validation failed. On success, the file has already been written to
    `config.SCREENSHOT_UPLOAD_DIR` under a random name and `error` is None.

    Validation order: extension allow-list first (cheap, rejects obvious
    junk fast), then size, then Pillow actually opening the bytes and
    reporting what format they really are -- the extension the browser
    reported is never trusted past this point. The name written to disk is
    derived from Pillow's detected format, not from the original filename
    or its extension, so a disguised file can't smuggle a dangerous
    extension onto the server even if it somehow passed the earlier checks.
    """
    if file_storage is None or not file_storage.filename:
        return None, None

    original_ext = _extension_of(file_storage.filename)
    if original_ext not in ALLOWED_SCREENSHOT_EXTENSIONS:
        return None, "Screenshot must be a PNG, JPG, GIF, or WEBP file."

    data = file_storage.read()
    if not data:
        return None, "Screenshot file is empty."
    if len(data) > MAX_SCREENSHOT_BYTES:
        max_mb = MAX_SCREENSHOT_BYTES // (1024 * 1024)
        return None, f"Screenshot must be smaller than {max_mb} MB."

    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()  # raises on a corrupt/non-image file; unusable after this
    except (UnidentifiedImageError, OSError, ValueError):
        return None, "That file is not a valid image."

    try:
        # verify() leaves the file object unusable, so re-open to read
        # attributes (format) safely.
        reopened = Image.open(io.BytesIO(data))
        detected_format = reopened.format
    except (UnidentifiedImageError, OSError, ValueError):
        return None, "That file is not a valid image."

    if detected_format not in ALLOWED_SCREENSHOT_FORMATS:
        return None, "Screenshot's actual content is not a supported image format."

    stored_ext = ALLOWED_SCREENSHOT_FORMATS[detected_format]
    stored_name = f"{secrets.token_hex(16)}{stored_ext}"

    config.SCREENSHOT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (config.SCREENSHOT_UPLOAD_DIR / stored_name).write_bytes(data)

    return stored_name, None


def delete_screenshot_file(filename: str | None) -> None:
    """Best-effort delete of a stored screenshot. Never raises -- an
    orphaned file on disk is a much smaller problem than failing a request
    over a cleanup step."""
    if not filename:
        return
    try:
        (config.SCREENSHOT_UPLOAD_DIR / filename).unlink(missing_ok=True)
    except OSError:
        pass


def _extension_of(filename: str) -> str:
    match = re.search(r"(\.[A-Za-z0-9]+)$", filename)
    return match.group(1).lower() if match else ""


def create_issue(
    organization_id: int, project: dict, reporter_id: int, cleaned: dict, screenshot_path: str | None
) -> tuple[int, str] | None:
    """Create an issue. Assumes `validate_issue` has already passed and
    `project` is the same organization-scoped project row it validated
    against."""
    result = issue_repository.create(
        organization_id=organization_id,
        project_id=project["id"],
        project_key=project["project_key"],
        issue_type=cleaned["issue_type"],
        parent_id=cleaned["parent_id"],
        title=cleaned["title"],
        description=cleaned["description"],
        reproduction_steps=cleaned["reproduction_steps"],
        category=cleaned["category"],
        priority=cleaned["priority"],
        severity=cleaned["severity"],
        status=DEFAULT_STATUS,
        reporter_id=reporter_id,
        screenshot_path=screenshot_path,
        labels=cleaned["labels"],
        story_points=cleaned["story_points"],
        due_date=cleaned["due_date"],
        fix_version_id=cleaned["fix_version_id"],
    )
    if result is not None:
        issue_id, issue_key = result
        # Stage 6: "every ... significant field edit is recorded in a
        # history/audit table" -- creation is the first such entry. Modeled
        # as a change_note-only row (no old/new status or assignment) so the
        # history panel renders it as a plain sentence, matching the spec's
        # own example note text ("Bug WEB-3 created").
        bug_history_repository.record(
            bug_id=issue_id,
            changed_by=reporter_id,
            change_note=f"created the issue ({issue_key})",
        )
    return result


def update_issue(
    issue_id: int,
    organization_id: int,
    cleaned: dict,
    screenshot_path: str | None,
    changed_by_user_id: int,
) -> bool:
    """Update an issue. Assumes `validate_issue` has already passed."""
    updated = issue_repository.update(
        issue_id=issue_id,
        organization_id=organization_id,
        parent_id=cleaned["parent_id"],
        title=cleaned["title"],
        description=cleaned["description"],
        reproduction_steps=cleaned["reproduction_steps"],
        category=cleaned["category"],
        priority=cleaned["priority"],
        severity=cleaned["severity"],
        screenshot_path=screenshot_path,
        labels=cleaned["labels"],
        story_points=cleaned["story_points"],
        due_date=cleaned["due_date"],
        fix_version_id=cleaned["fix_version_id"],
    )
    if updated:
        bug_history_repository.record(
            bug_id=issue_id,
            changed_by=changed_by_user_id,
            change_note="edited the issue",
        )
    return updated
