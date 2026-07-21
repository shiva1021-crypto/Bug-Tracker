"""SQL access for the `time_entries` table."""

from utils.db import get_connection


def create(bug_id: int, user_id: int, hours_spent, description: str | None) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO time_entries (bug_id, user_id, hours_spent, description) "
                "VALUES (%s, %s, %s, %s)",
                (bug_id, user_id, hours_spent, description),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def list_by_bug(bug_id: int, organization_id: int) -> list[dict]:
    """Chronological ascending (oldest first) -- the spec's own wording
    for this list ("a chronological list of past entries"), the same
    ordering convention `bug_history_repository.list_by_bug` already
    established for a timeline-shaped list."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT t.id, t.bug_id, t.user_id, t.hours_spent, t.description, t.logged_at,
                       u.full_name AS user_name
                FROM time_entries t
                JOIN users u ON u.id = t.user_id
                JOIN bugs b ON b.id = t.bug_id
                WHERE t.bug_id = %s AND b.organization_id = %s
                ORDER BY t.logged_at ASC
                """,
                (bug_id, organization_id),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
