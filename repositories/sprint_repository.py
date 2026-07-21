"""SQL access for the `sprints` table.

All direct database access for sprints lives here. Services call these
functions; routes never do. Every query is scoped by organization_id, the
tenant isolation boundary from Stage 3.
"""

from utils.db import get_connection

_COLUMNS = (
    "id, organization_id, project_id, name, goal, start_date, end_date, "
    "status, created_at"
)


def create(
    organization_id: int,
    project_id: int,
    name: str,
    goal: str | None,
    start_date,
    end_date,
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO sprints "
                "(organization_id, project_id, name, goal, start_date, end_date) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (organization_id, project_id, name, goal, start_date, end_date),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def get_by_id_and_org(sprint_id: int, organization_id: int) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"SELECT {_COLUMNS} FROM sprints WHERE id = %s AND organization_id = %s",
                (sprint_id, organization_id),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def list_by_project(project_id: int, organization_id: int, statuses: list[str] | None = None) -> list[dict]:
    """Sprints in one project, optionally restricted to a set of statuses
    (e.g. the backlog page only ever shows `future`/`active` sprints)."""
    query = f"SELECT {_COLUMNS} FROM sprints WHERE project_id = %s AND organization_id = %s"
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


def get_active_for_project(project_id: int, organization_id: int) -> dict | None:
    """The one `active` sprint in a project, or None. Used to enforce the
    "only one active sprint per project" rule before starting another."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"SELECT {_COLUMNS} FROM sprints "
                "WHERE project_id = %s AND organization_id = %s AND status = 'active'",
                (project_id, organization_id),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def set_status(sprint_id: int, organization_id: int, new_status: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE sprints SET status = %s WHERE id = %s AND organization_id = %s",
                (new_status, sprint_id, organization_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
