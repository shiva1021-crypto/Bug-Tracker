"""SQL access for the `comments` table.

All direct database access for comments lives here. Services call these
functions; routes never do. Every query joins back through `bugs` to check
organization_id -- comments have no organization_id column of their own,
so this join is how the tenant isolation boundary is enforced here too.
"""

from utils.db import get_connection


def create(bug_id: int, user_id: int, comment: str) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO comments (bug_id, user_id, comment) VALUES (%s, %s, %s)",
                (bug_id, user_id, comment),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def list_recent_by_user(user_id: int, organization_id: int, limit: int = 5) -> list[dict]:
    """Most recent comments this user has written, across every issue in
    their organization. Feeds the Stage 2 profile page's "Recent Comments"
    list (see reference-ui's profile.html)."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT c.id, c.bug_id, c.comment, c.created_at, b.title AS bug_title
                FROM comments c
                JOIN bugs b ON b.id = c.bug_id
                WHERE c.user_id = %s AND b.organization_id = %s
                ORDER BY c.created_at DESC
                LIMIT %s
                """,
                (user_id, organization_id, limit),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


def count_by_user(user_id: int, organization_id: int) -> int:
    """Total comment count for the profile page's "Comments Made" stat card."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT COUNT(*) FROM comments c
                JOIN bugs b ON b.id = c.bug_id
                WHERE c.user_id = %s AND b.organization_id = %s
                """,
                (user_id, organization_id),
            )
            return cursor.fetchone()[0]
        finally:
            cursor.close()


def list_by_bug(bug_id: int, organization_id: int) -> list[dict]:
    """Newest-first, per the spec's frontend section."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT c.id, c.bug_id, c.user_id, c.comment, c.created_at,
                       u.full_name AS author_name
                FROM comments c
                JOIN users u ON u.id = c.user_id
                JOIN bugs b ON b.id = c.bug_id
                WHERE c.bug_id = %s AND b.organization_id = %s
                ORDER BY c.created_at DESC
                """,
                (bug_id, organization_id),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
