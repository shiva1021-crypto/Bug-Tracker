"""SQL access for the `projects` table.

All direct database access for projects lives here. Services call these
functions; routes never do.

Every query is scoped by organization_id -- the tenant isolation boundary
from Stage 3, continued here for the first tenant-owned resource that isn't
a user or a registration request.
"""

from utils.db import get_connection


def list_by_organization(organization_id: int) -> list[dict]:
    """All projects in one organization, oldest first."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, organization_id, name, project_key, description, "
                "next_issue_number, created_at FROM projects "
                "WHERE organization_id = %s ORDER BY created_at ASC",
                (organization_id,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


def get_by_id_and_org(project_id: int, organization_id: int) -> dict | None:
    """Return a project only if it belongs to the given organization."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, organization_id, name, project_key, description, "
                "next_issue_number, created_at FROM projects "
                "WHERE id = %s AND organization_id = %s",
                (project_id, organization_id),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def key_exists(organization_id: int, project_key: str) -> bool:
    """True if this organization already has a project with this key.

    Scoped to organization_id -- two different organizations can each have
    a `WEB` project, per the spec's unique constraint on
    (organization_id, project_key).
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM projects WHERE organization_id = %s AND project_key = %s",
                (organization_id, project_key),
            )
            return cursor.fetchone() is not None
        finally:
            cursor.close()


def create(
    organization_id: int, name: str, project_key: str, description: str | None
) -> int:
    """Insert a new project and return its id.

    `next_issue_number` starts at 1 via the column default -- nothing
    creates issues until Stage 5, so there is nothing yet to allocate.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO projects (organization_id, name, project_key, description) "
                "VALUES (%s, %s, %s, %s)",
                (organization_id, name, project_key, description),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def allocate_next_issue_number(conn, project_id: int, organization_id: int) -> int | None:
    """Atomically claim and increment a project's next issue number.

    The Stage 4 spec calls this out explicitly under "Key business rule to
    implement carefully": issue-number allocation must read and increment
    `next_issue_number` inside the *same transaction* as the issue insert,
    using `SELECT ... FOR UPDATE` to lock the project's row -- otherwise two
    people creating issues in the same project at the same moment could be
    handed the same number.

    Unlike every other function in this module, this one does NOT open or
    commit its own connection: it takes an existing connection and must run
    inside the caller's transaction, which also inserts the issue row and
    commits both together. Nothing calls this yet -- Stage 5 is what
    creates issues -- but the locking contract belongs next to the table it
    locks, so it is implemented here now rather than invented from scratch
    later. Returns None if the project doesn't exist in that organization.
    """
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT next_issue_number FROM projects "
            "WHERE id = %s AND organization_id = %s FOR UPDATE",
            (project_id, organization_id),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        cursor.execute(
            "UPDATE projects SET next_issue_number = next_issue_number + 1 "
            "WHERE id = %s AND organization_id = %s",
            (project_id, organization_id),
        )
        return row["next_issue_number"]
    finally:
        cursor.close()
