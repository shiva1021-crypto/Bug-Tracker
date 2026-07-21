"""SQL access for the `email_outbox` table.

Deliberately has no `organization_id` -- an outbox row is a work item for
the background worker, not tenant data anyone browses. Writing a row here
(`create`) happens inline during a request (fast: one INSERT, no network
call); actually delivering it happens later, out of the request/response
cycle entirely, in `services/notification_worker.py`.
"""

from utils.db import get_connection


def create(to_email: str, subject: str, body: str) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO email_outbox (to_email, subject, body, status) "
                "VALUES (%s, %s, %s, 'pending')",
                (to_email, subject, body),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def list_pending(limit: int = 20) -> list[dict]:
    """Oldest-first batch of undelivered rows -- so a backlog drains in the
    order it was created, not newest-first."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, to_email, subject, body, status, created_at, sent_at "
                "FROM email_outbox WHERE status = 'pending' "
                "ORDER BY created_at ASC LIMIT %s",
                (limit,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


def mark_sent(outbox_id: int) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE email_outbox SET status = 'sent', sent_at = NOW() WHERE id = %s",
                (outbox_id,),
            )
            conn.commit()
        finally:
            cursor.close()


def mark_failed(outbox_id: int) -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE email_outbox SET status = 'failed' WHERE id = %s",
                (outbox_id,),
            )
            conn.commit()
        finally:
            cursor.close()


def count_by_status(status: str) -> int:
    """Used only by the verification harness/ops checks -- not on any hot
    request path."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM email_outbox WHERE status = %s", (status,))
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            cursor.close()
