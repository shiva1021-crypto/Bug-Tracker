"""SQL access for the `saved_filters` table.

`filter_data` is stored as a JSON column but travels through this module
as a Python dict on the way in and out -- `json.dumps`/`json.loads` happen
here, at the SQL boundary, so nothing above this layer needs to think
about serialization.
"""

import json

from utils.db import get_connection


def create(user_id: int, organization_id: int, name: str, filter_data: dict) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO saved_filters (user_id, organization_id, name, filter_data) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, organization_id, name, json.dumps(filter_data)),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def list_by_user(user_id: int, organization_id: int) -> list[dict]:
    """A user's own saved filters, oldest first. `is_shared` exists on the
    table (per the spec, "future: share with team") but nothing reads it
    yet -- every filter is private to the user who saved it until a later
    stage defines what sharing means."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, user_id, organization_id, name, filter_data, is_shared, created_at "
                "FROM saved_filters WHERE user_id = %s AND organization_id = %s "
                "ORDER BY created_at ASC",
                (user_id, organization_id),
            )
            rows = cursor.fetchall()
            for row in rows:
                raw = row["filter_data"]
                row["filter_data"] = json.loads(raw) if isinstance(raw, str) else (raw or {})
            return rows
        finally:
            cursor.close()
