"""SQL access for the `organizations` table.

All direct database access for organizations lives here. Services call these
functions; routes never do.
"""

from utils.db import get_connection


def get_by_name(name: str) -> dict | None:
    """Return the organization matching a name, or None.

    The table uses utf8mb4_unicode_ci collation (same as the rest of the
    schema), which compares case-insensitively -- "Acme" and "acme" resolve
    to the same organization here and collide on the UNIQUE index if someone
    tries to create both. That is intentional: it is the same mechanism that
    already made `users.email` a case-insensitive unique key in Stage 2, so
    no extra normalization code is needed for organization names either.
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, name, created_at FROM organizations WHERE name = %s",
                (name,),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def get_by_id(organization_id: int) -> dict | None:
    """Return the organization matching an id, or None."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, name, created_at FROM organizations WHERE id = %s",
                (organization_id,),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def create(name: str) -> int:
    """Insert a new organization and return its id."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO organizations (name) VALUES (%s)", (name,))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
