"""SQL access for the `bug_history` table.

Records status changes, assignment changes, and other significant edits to
an issue. Ordered chronologically ascending (oldest first) -- deliberately
the opposite order from comments, since a history panel reads naturally as
a timeline while comments read naturally newest-first.
"""

from utils.db import get_connection


def record(
    bug_id: int,
    changed_by: int,
    old_status: str | None = None,
    new_status: str | None = None,
    old_assigned_to: int | None = None,
    new_assigned_to: int | None = None,
    change_note: str = "",
) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO bug_history (
                    bug_id, changed_by, old_status, new_status,
                    old_assigned_to, new_assigned_to, change_note
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    bug_id,
                    changed_by,
                    old_status,
                    new_status,
                    old_assigned_to,
                    new_assigned_to,
                    change_note,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def list_by_bug(bug_id: int, organization_id: int) -> list[dict]:
    """Chronological ascending (oldest first)."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT h.id, h.bug_id, h.changed_by, h.old_status, h.new_status,
                       h.old_assigned_to, h.new_assigned_to, h.change_note,
                       h.changed_at,
                       changer.full_name AS changed_by_name,
                       old_user.full_name AS old_assigned_to_name,
                       new_user.full_name AS new_assigned_to_name
                FROM bug_history h
                JOIN bugs b ON b.id = h.bug_id
                JOIN users changer ON changer.id = h.changed_by
                LEFT JOIN users old_user ON old_user.id = h.old_assigned_to
                LEFT JOIN users new_user ON new_user.id = h.new_assigned_to
                WHERE h.bug_id = %s AND b.organization_id = %s
                ORDER BY h.changed_at ASC
                """,
                (bug_id, organization_id),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
