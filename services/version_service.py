"""Version/release business rules: validation, visibility, and the
unreleased -> released / -> archived transitions.

Creating, releasing, and archiving a version is Admin/PM-only, the same
tier as sprint and custom-field management (all three follow the Stage 3
"organization owner" permission tier this codebase has used consistently
since Stage 4's project creation).
"""

from datetime import datetime

from repositories import issue_repository, user_repository, version_repository

CAN_MANAGE_VERSIONS_ROLES = {"admin", "project_manager"}

MAX_NAME_LENGTH = 120

# Versions page's main list -- per the spec, "archiving a version hides it
# from the main list." Archived versions still exist and are still valid
# historical `fix_version_id` targets on whatever issues already point to
# them (see `routes/version_routes.py` and `templates/versions.html` for
# where this matters); they just stop appearing here.
VISIBLE_STATUSES = ["unreleased", "released"]


def verify_version_manager(user_id: int) -> dict | None:
    user = user_repository.get_by_id(user_id)
    if user is None or user["role"] not in CAN_MANAGE_VERSIONS_ROLES:
        return None
    return user


def validate_version(name: str, release_date_raw: str) -> tuple[list[str], dict]:
    errors: list[str] = []

    name = (name or "").strip()
    if not name:
        errors.append("Version name is required.")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"Version name must be {MAX_NAME_LENGTH} characters or fewer.")

    release_date = None
    release_date_raw = (release_date_raw or "").strip()
    if release_date_raw:
        try:
            release_date = datetime.strptime(release_date_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Enter a valid release date.")

    return errors, {"name": name, "release_date": release_date}


def create_version(organization_id: int, project_id: int, cleaned: dict) -> tuple[bool, str | None]:
    if version_repository.name_exists(project_id, cleaned["name"]):
        return False, f'A version named "{cleaned["name"]}" already exists in this project.'

    version_repository.create(
        organization_id=organization_id,
        project_id=project_id,
        name=cleaned["name"],
        release_date=cleaned["release_date"],
    )
    return True, None


def get_version(version_id: int, organization_id: int) -> dict | None:
    return version_repository.get_by_id_and_org(version_id, organization_id)


def list_visible_versions(project_id: int, organization_id: int) -> list[dict]:
    """Unreleased first, then released -- the versions page's main list."""
    versions = version_repository.list_by_project(project_id, organization_id, VISIBLE_STATUSES)
    return sorted(versions, key=lambda v: (0 if v["status"] == "unreleased" else 1, v["created_at"]))


def list_selectable_versions(project_id: int, organization_id: int) -> list[dict]:
    """Versions a user could pick as an issue's *new* fix version -- same
    as the visible list, since an archived version shouldn't be newly
    assignable even though one already linked to an issue stays linked
    (see `services/issue_service.py`'s validate_issue, which allows an
    issue's *current* fix version through even if it isn't in this list)."""
    return list_visible_versions(project_id, organization_id)


def release_version(version: dict, manager_user: dict) -> tuple[bool, str | None]:
    if version["status"] != "unreleased":
        return False, "Only an unreleased version can be released."

    updated = version_repository.set_status(version["id"], version["organization_id"], "released")
    if not updated:
        return False, "Could not release the version -- it may no longer exist."
    return True, None


def archive_version(version: dict, manager_user: dict) -> tuple[bool, str | None]:
    if version["status"] == "archived":
        return False, "This version is already archived."

    updated = version_repository.set_status(version["id"], version["organization_id"], "archived")
    if not updated:
        return False, "Could not archive the version -- it may no longer exist."
    return True, None


def issue_counts(version_id: int, organization_id: int) -> dict:
    return issue_repository.count_by_fix_version(version_id, organization_id)
