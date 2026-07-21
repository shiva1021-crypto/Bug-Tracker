"""SQL access for the `auth_rate_limits` table -- the database-backed rate
limit storage, used when `RATELIMIT_STORAGE=database` (see
`services/rate_limit_service.py`). Not organization-scoped: `identifier` is
a plain IP address or normalized email, shared across every organization,
since brute-forcing login/registration isn't a tenant-scoped concern.
"""

from utils.db import get_connection


def get(identifier: str) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, identifier, attempt_count, window_started_at "
                "FROM auth_rate_limits WHERE identifier = %s",
                (identifier,),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def upsert_increment(identifier: str, window_started_at) -> None:
    """Insert a fresh row at count 1 for a never-seen identifier, or bump
    an existing one's `attempt_count` by 1. `window_started_at` is only
    used on first insert -- `reset_window` is what rewrites it once a
    window has expired, so a plain increment never resets the clock."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO auth_rate_limits (identifier, attempt_count, window_started_at) "
                "VALUES (%s, 1, %s) "
                "ON DUPLICATE KEY UPDATE attempt_count = attempt_count + 1",
                (identifier, window_started_at),
            )
            conn.commit()
        finally:
            cursor.close()


def reset_window(identifier: str, window_started_at) -> None:
    """Start a fresh window for this identifier: count back to 1 (this
    call itself represents the first attempt of the new window)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO auth_rate_limits (identifier, attempt_count, window_started_at) "
                "VALUES (%s, 1, %s) "
                "ON DUPLICATE KEY UPDATE attempt_count = 1, window_started_at = VALUES(window_started_at)",
                (identifier, window_started_at),
            )
            conn.commit()
        finally:
            cursor.close()


def clear(identifier: str) -> None:
    """Forget this identifier entirely -- called on a successful
    login/registration so a legitimate user's next attempt starts clean."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM auth_rate_limits WHERE identifier = %s", (identifier,))
            conn.commit()
        finally:
            cursor.close()
