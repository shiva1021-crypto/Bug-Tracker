"""SQL access for `automation_rules`.

`conditions` and `actions` travel through this module as Python lists (of
dicts) on the way in and out -- JSON (de)serialization happens here, at
the SQL boundary, same convention as `saved_filter_repository`.
`project_id` is nullable: NULL means "applies to every project in the
organization," per the spec.
"""

import json

from utils.db import get_connection

_COLUMNS = (
    "id, organization_id, project_id, name, trigger_event, conditions, "
    "actions, enabled, created_at"
)


def _deserialize(row: dict) -> dict:
    row["conditions"] = json.loads(row["conditions"]) if row["conditions"] else []
    row["actions"] = json.loads(row["actions"]) if row["actions"] else []
    row["enabled"] = bool(row["enabled"])
    return row


def create(
    organization_id: int,
    project_id: int | None,
    name: str,
    trigger_event: str,
    conditions: list[dict],
    actions: list[dict],
    enabled: bool = True,
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO automation_rules "
                "(organization_id, project_id, name, trigger_event, conditions, actions, enabled) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    organization_id,
                    project_id,
                    name,
                    trigger_event,
                    json.dumps(conditions),
                    json.dumps(actions),
                    1 if enabled else 0,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def get_by_id_and_org(rule_id: int, organization_id: int) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"SELECT {_COLUMNS} FROM automation_rules WHERE id = %s AND organization_id = %s",
                (rule_id, organization_id),
            )
            row = cursor.fetchone()
            return _deserialize(row) if row else None
        finally:
            cursor.close()


def list_by_organization(organization_id: int) -> list[dict]:
    """Every rule in the org (any project scope, enabled or not) -- for
    the `/automation` management page."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"SELECT {_COLUMNS} FROM automation_rules WHERE organization_id = %s "
                "ORDER BY created_at ASC",
                (organization_id,),
            )
            return [_deserialize(row) for row in cursor.fetchall()]
        finally:
            cursor.close()


def list_matching(organization_id: int, project_id: int, trigger_event: str) -> list[dict]:
    """Enabled rules that apply to one project/trigger -- either scoped to
    that exact project, or org-wide (`project_id IS NULL`). This is the
    automation engine's one read query, per the spec's design note
    ("fetch enabled rules matching the org/project/trigger")."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"SELECT {_COLUMNS} FROM automation_rules "
                "WHERE organization_id = %s AND trigger_event = %s AND enabled = 1 "
                "AND (project_id IS NULL OR project_id = %s) "
                "ORDER BY id ASC",
                (organization_id, trigger_event, project_id),
            )
            return [_deserialize(row) for row in cursor.fetchall()]
        finally:
            cursor.close()


def update(
    rule_id: int,
    organization_id: int,
    project_id: int | None,
    name: str,
    trigger_event: str,
    conditions: list[dict],
    actions: list[dict],
) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE automation_rules SET "
                "  project_id = %s, name = %s, trigger_event = %s, "
                "  conditions = %s, actions = %s "
                "WHERE id = %s AND organization_id = %s",
                (
                    project_id,
                    name,
                    trigger_event,
                    json.dumps(conditions),
                    json.dumps(actions),
                    rule_id,
                    organization_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()


def set_enabled(rule_id: int, organization_id: int, enabled: bool) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE automation_rules SET enabled = %s WHERE id = %s AND organization_id = %s",
                (1 if enabled else 0, rule_id, organization_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()


def delete(rule_id: int, organization_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM automation_rules WHERE id = %s AND organization_id = %s",
                (rule_id, organization_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
