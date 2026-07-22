"""SQL access for the `users` table.

All direct database access for users lives here. Services call these
functions; routes never do.

`email` stays a global lookup (not organization-scoped): a user does not
know their organization until after they are found by email and
authenticated and `users.email` is globally UNIQUE by design (one email,
one account, one organization). Every query that reads or writes org-scoped
*data* -- the member list, role changes -- filters by organization_id;
that is the tenant isolation boundary introduced in this stage.
"""

from utils.db import get_connection


def get_by_email(email: str) -> dict | None:
    """Return the user row matching an email, or None."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, full_name, email, password_hash, organization_id, "
                "role, created_at FROM users WHERE email = %s",
                (email,),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def get_by_id(user_id: int) -> dict | None:
    """Return the user row matching an id, or None.

    Never selects password_hash -- callers of this function display data or
    check the current role, they never authenticate with it.
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, full_name, email, organization_id, role, created_at "
                "FROM users WHERE id = %s",
                (user_id,),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def get_by_id_and_org(user_id: int, organization_id: int) -> dict | None:
    """Return a user only if they belong to the given organization.

    Used before acting on a client-supplied user id (e.g. changing someone's
    role) so an admin can never reach into another organization by guessing
    an id.
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, full_name, email, organization_id, role, created_at "
                "FROM users WHERE id = %s AND organization_id = %s",
                (user_id, organization_id),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def list_by_organization(organization_id: int) -> list[dict]:
    """All members of one organization, oldest first."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, full_name, email, role, created_at FROM users "
                "WHERE organization_id = %s ORDER BY created_at ASC",
                (organization_id,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


def email_exists(email: str) -> bool:
    """True if an account already uses this email, in any organization."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM users WHERE email = %s", (email,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()


def update_role(user_id: int, organization_id: int, new_role: str) -> bool:
    """Change a user's role. Scoped to organization_id. Returns True if a
    row changed (i.e. the user really is a member of that organization)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET role = %s WHERE id = %s AND organization_id = %s",
                (new_role, user_id, organization_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()


def create(
    full_name: str,
    email: str,
    password_hash: str,
    organization_id: int,
    role: str,
) -> int:
    """Insert a new user and return its id.

    Only ever receives an already-hashed password -- hashing is the service
    layer's job and a plaintext password must never reach this module.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users "
                "(full_name, email, password_hash, organization_id, role) "
                "VALUES (%s, %s, %s, %s, %s)",
                (full_name, email, password_hash, organization_id, role),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
