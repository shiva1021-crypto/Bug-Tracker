"""MySQL connection pooling.

Cross-cutting DB plumbing: a single lazily-created connection pool that the
rest of the app borrows connections from. We never hold one long-lived
connection; each caller checks a connection out of the pool and returns it.
"""

from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling

from config import config

_POOL_NAME = "bug_tracker_pool"
_pool = None


def get_pool() -> pooling.MySQLConnectionPool:
    """Return the process-wide connection pool, creating it on first use."""
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name=_POOL_NAME,
            pool_size=config.DB_POOL_SIZE,
            pool_reset_session=True,
            **config.db_connection_kwargs(include_database=True),
        )
    return _pool


@contextmanager
def get_connection():
    """Borrow a pooled connection and guarantee it is returned to the pool.

    Usage:
        with get_connection() as conn:
            cursor = conn.cursor()
            ...
    """
    conn = get_pool().get_connection()
    try:
        yield conn
    finally:
        # For a pooled connection, close() returns it to the pool rather than
        # tearing down the underlying socket.
        conn.close()
