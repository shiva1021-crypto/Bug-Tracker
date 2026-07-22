"""Custom-field business rules: definition CRUD and validating/persisting
per-issue values.

Definitions are always project-specific (per the spec: "Admin/PM can
define project-specific fields") -- there is no org-wide custom field.
Managing definitions is gated the same way sprint/version management is:
a fresh `verify_field_manager()` check, Admin/PM only.
"""

from datetime import datetime

from repositories import custom_field_repository, user_repository

FIELD_TYPES = ["text", "number", "date", "dropdown", "checkbox"]

CAN_MANAGE_FIELDS_ROLES = {"admin", "project_manager"}

MAX_NAME_LENGTH = 120
MIN_DROPDOWN_OPTIONS = 2


def verify_field_manager(user_id: int) -> dict | None:
    """Fresh DB check: the user row if they may define/delete custom
    fields for a project, else None."""
    user = user_repository.get_by_id(user_id)
    if user is None or user["role"] not in CAN_MANAGE_FIELDS_ROLES:
        return None
    return user


def list_fields(project_id: int, organization_id: int) -> list[dict]:
    return custom_field_repository.list_definitions(project_id, organization_id)


def get_field(field_id: int, organization_id: int) -> dict | None:
    return custom_field_repository.get_definition(field_id, organization_id)


def validate_field(
    name: str, field_type: str, options_raw: str, required_raw: str
) -> tuple[list[str], dict]:
    errors: list[str] = []

    name = (name or "").strip()
    if not name:
        errors.append("Field name is required.")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"Field name must be {MAX_NAME_LENGTH} characters or fewer.")

    if field_type not in FIELD_TYPES:
        errors.append("Select a valid field type.")

    options: list[str] | None = None
    if field_type == "dropdown":
        options = [line.strip() for line in (options_raw or "").splitlines() if line.strip()]
        if len(options) < MIN_DROPDOWN_OPTIONS:
            errors.append(f"Dropdown fields need at least {MIN_DROPDOWN_OPTIONS} options (one per line).")

    required = required_raw in ("on", "true", "1")

    cleaned = {"name": name, "field_type": field_type, "options": options, "required": required}
    return errors, cleaned


def create_field(organization_id: int, project_id: int, cleaned: dict) -> int:
    display_order = custom_field_repository.count_definitions(project_id, organization_id)
    return custom_field_repository.create_definition(
        organization_id=organization_id,
        project_id=project_id,
        name=cleaned["name"],
        field_type=cleaned["field_type"],
        options=cleaned["options"],
        required=cleaned["required"],
        display_order=display_order,
    )


def delete_field(field_id: int, organization_id: int) -> bool:
    """Delete a field definition. Its stored values on every issue are
    removed automatically by `custom_field_values.field_id`'s
    `ON DELETE CASCADE` -- nothing here loops over issues one at a time,
    which is what keeps this a single statement that can never partially
    fail partway through a large project."""
    return custom_field_repository.delete_definition(field_id, organization_id)


def list_values_for_issue(issue_id: int, organization_id: int) -> list[dict]:
    return custom_field_repository.list_values_for_issue(issue_id, organization_id)


def _validate_and_collect(fields: list[dict], form) -> tuple[list[str], dict[int, str | None]]:
    errors: list[str] = []
    values: dict[int, str | None] = {}

    for field in fields:
        raw = str(form.get(f"custom_field_{field['id']}", "") or "").strip()

        if field["field_type"] == "checkbox":
            values[field["id"]] = "1" if raw in ("on", "true", "1") else "0"
            continue

        if not raw:
            if field["required"]:
                errors.append(f'"{field["name"]}" is required.')
            values[field["id"]] = None
            continue

        if field["field_type"] == "number":
            try:
                float(raw)
            except ValueError:
                errors.append(f'"{field["name"]}" must be a number.')
                continue
        elif field["field_type"] == "date":
            try:
                datetime.strptime(raw, "%Y-%m-%d")
            except ValueError:
                errors.append(f'"{field["name"]}" must be a valid date.')
                continue
        elif field["field_type"] == "dropdown":
            if raw not in (field["options"] or []):
                errors.append(f'"{field["name"]}" must be one of its defined options.')
                continue

        values[field["id"]] = raw

    return errors, values


def validate_values(project_id: int, organization_id: int, form) -> list[str]:
    """Validation-only pass over a submitted form's custom field values,
    with nothing persisted. Used on issue *creation*, where there is no
    issue id yet to attach values to -- `save_values` (which both
    validates and persists) can only run after the issue row exists, so
    the create route validates with this first and only creates the issue
    once these errors come back empty.
    """
    fields = list_fields(project_id, organization_id)
    errors, _values = _validate_and_collect(fields, form)
    return errors


def save_values(
    issue_id: int, organization_id: int, project_id: int, form
) -> tuple[list[str], list[dict]]:
    """Validate and persist every custom field value submitted for one
    issue. Returns `(errors, changes)` -- `changes` lists every field
    whose value actually differs from what was stored before (empty on
    creation, since there is nothing to compare against yet), which is
    what `routes/issue_routes.py::edit_issue` uses to fire the
    `field_updated` automation trigger per changed field.
    """
    fields = list_fields(project_id, organization_id)
    errors, values = _validate_and_collect(fields, form)
    if errors:
        return errors, []

    existing = {
        row["id"]: row["value"] for row in custom_field_repository.list_values_for_issue(
            issue_id, organization_id
        )
    } if issue_id else {}

    changes: list[dict] = []
    for field in fields:
        new_value = values[field["id"]]
        old_value = existing.get(field["id"])
        if new_value != old_value:
            changes.append(
                {"field_name": field["name"], "old_value": old_value, "new_value": new_value}
            )
        custom_field_repository.set_value(issue_id, field["id"], new_value)

    return [], changes
