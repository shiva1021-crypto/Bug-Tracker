"""SQL access for the `dashboard_widgets` table.

A row with `user_id IS NULL` is an organization's *default* widget: the
layout every new member sees until they personally customize their own
dashboard. A row with `user_id` set is one specific user's personal
widget. `services/dashboard_service.py` is what decides which set to read
for a given viewer and when to "fork" the org defaults into a personal
set -- this module only stores and fetches rows exactly as asked.
"""

import json

from utils.db import get_connection


def _parse_config(row: dict) -> dict:
    raw = row.get("config")
    row["config"] = json.loads(raw) if isinstance(raw, str) else (raw or {})
    return row


def list_for_user(organization_id: int, user_id: int) -> list[dict]:
    """One user's personal widget layout, in position order. Empty if they
    have never customized their dashboard -- callers fall back to
    `list_org_defaults()` in that case."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, organization_id, user_id, widget_type, title, config, position, width "
                "FROM dashboard_widgets WHERE organization_id = %s AND user_id = %s "
                "ORDER BY position ASC, id ASC",
                (organization_id, user_id),
            )
            return [_parse_config(row) for row in cursor.fetchall()]
        finally:
            cursor.close()


def list_org_defaults(organization_id: int) -> list[dict]:
    """The organization-wide default layout (`user_id IS NULL`), in
    position order."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, organization_id, user_id, widget_type, title, config, position, width "
                "FROM dashboard_widgets WHERE organization_id = %s AND user_id IS NULL "
                "ORDER BY position ASC, id ASC",
                (organization_id,),
            )
            return [_parse_config(row) for row in cursor.fetchall()]
        finally:
            cursor.close()


def count_org_defaults(organization_id: int) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM dashboard_widgets WHERE organization_id = %s AND user_id IS NULL",
                (organization_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            cursor.close()


def create(
    organization_id: int,
    user_id: int | None,
    widget_type: str,
    title: str,
    config: dict | None,
    position: int,
    width: str,
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO dashboard_widgets "
                "(organization_id, user_id, widget_type, title, config, position, width) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    organization_id,
                    user_id,
                    widget_type,
                    title,
                    json.dumps(config) if config is not None else None,
                    position,
                    width,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def get_by_id_and_user(widget_id: int, organization_id: int, user_id: int) -> dict | None:
    """A specific *personal* widget row -- used before deleting one, so a
    user can never remove another user's (or the org default's) row by
    guessing an id."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, organization_id, user_id, widget_type, title, config, position, width "
                "FROM dashboard_widgets WHERE id = %s AND organization_id = %s AND user_id = %s",
                (widget_id, organization_id, user_id),
            )
            row = cursor.fetchone()
            return _parse_config(row) if row else None
        finally:
            cursor.close()


def delete(widget_id: int, organization_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM dashboard_widgets WHERE id = %s AND organization_id = %s AND user_id = %s",
                (widget_id, organization_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()


def max_position_for_user(organization_id: int, user_id: int) -> int:
    """Highest `position` currently used in this user's personal layout,
    or -1 if they have none -- used to append a new widget at the end
    without disturbing the rest of the layout's order."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COALESCE(MAX(position), -1) FROM dashboard_widgets "
                "WHERE organization_id = %s AND user_id = %s",
                (organization_id, user_id),
            )
            row = cursor.fetchone()
            return row[0] if row else -1
        finally:
            cursor.close()
