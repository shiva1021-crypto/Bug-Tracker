"""SQL access for the `versions` table.

`description` is a real column on this table (per the spec's own data
model) but nothing in this stage's frontend ever sets it -- see
`services/version_service.py`'s docstring for why. `create()` still
accepts it (defaulting to `None`) rather than hardcoding it out of the
SQL entirely, so the column isn't dead weight if a later stage wants to
populate it.
"""

from utils.db import get_connection

_COLUMNS = (
    "id, organization_id, project_id, name, description, release_date, "
    "status, created_at"
)


def create(
    organization_id: int,
    project_id: int,
    name: str,
    description: str | None = None,
    release_date=None,
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO versions (organization_id, project_id, name, description, release_date) "
                "VALUES (%s, %s, %s, %s, %s)",
                (organization_id, project_id, name, description, release_date),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def get_by_id_and_org(version_id: int, organization_id: int) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"SELECT {_COLUMNS} FROM versions WHERE id = %s AND organization_id = %s",
                (version_id, organization_id),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def list_by_project(project_id: int, organization_id: int, statuses: list[str] | None = None) -> list[dict]:
    query = f"SELECT {_COLUMNS} FROM versions WHERE project_id = %s AND organization_id = %s"
    params: list = [project_id, organization_id]
    if statuses:
        placeholders = ", ".join(["%s"] * len(statuses))
        query += f" AND status IN ({placeholders})"
        params.extend(statuses)
    query += " ORDER BY created_at ASC"

    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, tuple(params))
            return cursor.fetchall()
        finally:
            cursor.close()


def name_exists(project_id: int, name: str) -> bool:
    """True if this project already has a version with this name -- the
    spec's `UNIQUE (project_id, name)` constraint, pre-checked here the
    same way `project_repository.key_exists` pre-checks project keys."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM versions WHERE project_id = %s AND name = %s",
                (project_id, name),
            )
            return cursor.fetchone() is not None
        finally:
            cursor.close()


def set_status(version_id: int, organization_id: int, new_status: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE versions SET status = %s WHERE id = %s AND organization_id = %s",
                (new_status, version_id, organization_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
