"""SQL access for `custom_field_definitions` and `custom_field_values`.

All direct database access for custom fields lives here. Services call
these functions; routes never do. Definitions are always project-scoped
(no org-wide custom fields, per the spec); values carry no
`organization_id` of their own and are always reached through a join back
to `bugs`/`custom_field_definitions`, the same pattern Stage 6's
`comments`/`bug_history` and Stage 8's `issue_links` already use.
"""

import json

from utils.db import get_connection


def create_definition(
    organization_id: int,
    project_id: int,
    name: str,
    field_type: str,
    options: list[str] | None,
    required: bool,
    display_order: int,
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO custom_field_definitions "
                "(organization_id, project_id, name, field_type, options, required, display_order) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    organization_id,
                    project_id,
                    name,
                    field_type,
                    json.dumps(options) if options is not None else None,
                    1 if required else 0,
                    display_order,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def _parse_options(row: dict) -> dict:
    raw = row.get("options")
    if raw is None:
        row["options"] = None
    elif isinstance(raw, str):
        row["options"] = json.loads(raw)
    row["required"] = bool(row["required"])
    return row


def list_definitions(project_id: int, organization_id: int) -> list[dict]:
    """A project's custom field definitions, in display order."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, organization_id, project_id, name, field_type, options, "
                "required, display_order, created_at FROM custom_field_definitions "
                "WHERE project_id = %s AND organization_id = %s "
                "ORDER BY display_order ASC, id ASC",
                (project_id, organization_id),
            )
            return [_parse_options(row) for row in cursor.fetchall()]
        finally:
            cursor.close()


def get_definition(field_id: int, organization_id: int) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, organization_id, project_id, name, field_type, options, "
                "required, display_order, created_at FROM custom_field_definitions "
                "WHERE id = %s AND organization_id = %s",
                (field_id, organization_id),
            )
            row = cursor.fetchone()
            return _parse_options(row) if row else None
        finally:
            cursor.close()


def count_definitions(project_id: int, organization_id: int) -> int:
    """Used to compute the next `display_order` for a new field."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM custom_field_definitions "
                "WHERE project_id = %s AND organization_id = %s",
                (project_id, organization_id),
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            cursor.close()


def delete_definition(field_id: int, organization_id: int) -> bool:
    """Delete a field definition. `custom_field_values.field_id`'s
    `ON DELETE CASCADE` is what actually removes every stored value for
    this field on every issue that had one -- there is no application-code
    loop deleting values one at a time."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM custom_field_definitions WHERE id = %s AND organization_id = %s",
                (field_id, organization_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()


def set_value(bug_id: int, field_id: int, value: str | None) -> None:
    """Insert or update one field's value on one issue."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO custom_field_values (bug_id, field_id, value) "
                "VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE value = VALUES(value)",
                (bug_id, field_id, value),
            )
            conn.commit()
        finally:
            cursor.close()


def list_values_for_issue(bug_id: int, organization_id: int) -> list[dict]:
    """Every custom field defined for this issue's project, each paired
    with its stored value (None if never set) -- a LEFT JOIN so a field
    added after the issue was created still shows up, just blank."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT d.id, d.name, d.field_type, d.options, d.required, d.display_order,
                       v.value AS value
                FROM custom_field_definitions d
                JOIN bugs b ON b.project_id = d.project_id
                LEFT JOIN custom_field_values v ON v.field_id = d.id AND v.bug_id = b.id
                WHERE b.id = %s AND d.organization_id = %s
                ORDER BY d.display_order ASC, d.id ASC
                """,
                (bug_id, organization_id),
            )
            return [_parse_options(row) for row in cursor.fetchall()]
        finally:
            cursor.close()
