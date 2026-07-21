"""SQL access for the `users` table.

All direct database access for users lives here. Services call these functions;
routes never do.
"""

from utils.db import get_connection


def get_by_email(email: str) -> dict | None:
    """Return the user row matching an email, or None."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, full_name, email, password_hash, created_at "
                "FROM users WHERE email = %s",
                (email,),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def get_by_id(user_id: int) -> dict | None:
    """Return the user row matching an id, or None.

    Never selects password_hash — callers of this function display data.
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, full_name, email, created_at FROM users WHERE id = %s",
                (user_id,),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def email_exists(email: str) -> bool:
    """True if an account already uses this email."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM users WHERE email = %s", (email,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()


def create(full_name: str, email: str, password_hash: str) -> int:
    """Insert a new user and return its id.

    Only ever receives an already-hashed password — hashing is the service
    layer's job, and a plaintext password must never reach this module.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (full_name, email, password_hash) "
                "VALUES (%s, %s, %s)",
                (full_name, email, password_hash),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
