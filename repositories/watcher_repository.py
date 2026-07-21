"""SQL access for the `issue_watchers` table."""

from utils.db import get_connection


def is_watching(bug_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM issue_watchers WHERE bug_id = %s AND user_id = %s",
                (bug_id, user_id),
            )
            return cursor.fetchone() is not None
        finally:
            cursor.close()


def add(bug_id: int, user_id: int) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT IGNORE INTO issue_watchers (bug_id, user_id) VALUES (%s, %s)",
                (bug_id, user_id),
            )
            conn.commit()
        finally:
            cursor.close()


def remove(bug_id: int, user_id: int) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM issue_watchers WHERE bug_id = %s AND user_id = %s",
                (bug_id, user_id),
            )
            conn.commit()
        finally:
            cursor.close()


def count(bug_id: int) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM issue_watchers WHERE bug_id = %s",
                (bug_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            cursor.close()
