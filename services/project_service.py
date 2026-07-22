"""Project business rules: creation, validation and organization scoping.

Only Admins and Project Managers may create a project. That is enforced
here with a fresh database read (`verify_project_creator`), the same
pattern `services/admin_service.py::verify_admin` uses -- the session's
cached role is fine for showing or hiding the "+ New Project" button, but
the actual permission check always re-reads the role, so a role change
takes effect on the user's very next request just like the admin panel.
"""

import re

from repositories import issue_repository, project_repository, user_repository

PROJECT_KEY_PATTERN = re.compile(r"^[A-Z]{2,6}$")
MAX_PROJECT_NAME_LENGTH = 150

# The same two roles the Stage 3 permission matrix grants "Manage sprints"
# to -- project creation sits at that tier of action.
CAN_CREATE_PROJECT_ROLES = {"admin", "project_manager"}

DEFAULT_PROJECT_NAME = "General"
DEFAULT_PROJECT_KEY = "GEN"
DEFAULT_PROJECT_DESCRIPTION = (
    "The default project created automatically for your organization."
)


def verify_project_creator(user_id: int) -> dict | None:
    """Fresh DB check: the user row if they may create a project, else None."""
    user = user_repository.get_by_id(user_id)
    if user is None or user["role"] not in CAN_CREATE_PROJECT_ROLES:
        return None
    return user


def list_projects(organization_id: int) -> list[dict]:
    """Every project in the organization, each annotated with `issue_count`
    for the Projects list page's card footer (see reference-ui's
    projects.html)."""
    projects = project_repository.list_by_organization(organization_id)
    counts = issue_repository.count_by_project(organization_id)
    for project in projects:
        project["issue_count"] = counts.get(project["id"], 0)
    return projects


def get_project(project_id: int, organization_id: int) -> dict | None:
    return project_repository.get_by_id_and_org(project_id, organization_id)


def validate_project(name: str, project_key: str, organization_id: int) -> list[str]:
    """Server-side validation for project creation. Returns a list of errors."""
    errors: list[str] = []

    name = (name or "").strip()
    project_key = (project_key or "").strip().upper()

    if not name:
        errors.append("Project name is required.")
    elif len(name) > MAX_PROJECT_NAME_LENGTH:
        errors.append(f"Project name must be {MAX_PROJECT_NAME_LENGTH} characters or fewer.")

    if not project_key:
        errors.append("Project key is required.")
    elif not PROJECT_KEY_PATTERN.match(project_key):
        errors.append("Project key must be 2-6 letters (A-Z).")
    elif project_repository.key_exists(organization_id, project_key):
        errors.append(
            f'A project with the key "{project_key}" already exists in your organization.'
        )

    return errors


def create_project(
    organization_id: int, name: str, project_key: str, description: str
) -> int:
    """Create a project. Assumes `validate_project` has already passed.

    The key is normalized to uppercase here regardless of how it was typed
    -- the form's helper text says it will be and the column itself is
    documented as always-uppercase, so this is the single place that
    guarantee is honored rather than trusting the caller to have done it.
    """
    return project_repository.create(
        organization_id=organization_id,
        name=name.strip(),
        project_key=project_key.strip().upper(),
        description=(description or "").strip() or None,
    )


def create_default_project(organization_id: int) -> int:
    """Auto-create the "General" project for a brand-new organization.

    Called once, immediately after `organization_repository.create()`, from
    `auth_service.register()`'s new-organization path -- so `GEN` can never
    collide with an existing key (the organization has no projects yet).
    """
    return project_repository.create(
        organization_id=organization_id,
        name=DEFAULT_PROJECT_NAME,
        project_key=DEFAULT_PROJECT_KEY,
        description=DEFAULT_PROJECT_DESCRIPTION,
    )
