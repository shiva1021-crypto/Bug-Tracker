"""SQL-layer health checks.

The repository layer owns all direct database access. For Stage 1 there are no
tables yet, so the only "query" is a trivial round-trip that proves a pooled
connection can be opened, used and closed.
"""

from utils.db import get_connection


def ping() -> None:
    """Open a pooled connection, run `SELECT 1` and close it.

    Raises the underlying database error if the connection cannot be made or the
    query fails. Returns None on success.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        finally:
            cursor.close()
