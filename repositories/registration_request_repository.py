"""SQL access for the `registration_requests` table.

All direct database access for registration requests lives here. Services
call these functions; routes never do.

Every query that reads or mutates a specific request is scoped by
organization_id -- this is the tenant isolation boundary from Stage 3
onward and it is what stops an admin from one organization approving or
even seeing a request that belongs to another.
"""

from utils.db import get_connection


def create(
    organization_id: int,
    full_name: str,
    email: str,
    password_hash: str,
    requested_role: str,
    requester_ip: str | None,
) -> int:
    """Insert a new pending registration request and return its id."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO registration_requests "
                "(organization_id, full_name, email, password_hash, "
                " requested_role, requester_ip, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'pending')",
                (
                    organization_id,
                    full_name,
                    email,
                    password_hash,
                    requested_role,
                    requester_ip,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def get_by_id_and_org(request_id: int, organization_id: int) -> dict | None:
    """Return a request only if it belongs to the given organization."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, organization_id, full_name, email, password_hash, "
                "requested_role, requester_ip, status, created_at "
                "FROM registration_requests WHERE id = %s AND organization_id = %s",
                (request_id, organization_id),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def list_pending_by_organization(organization_id: int) -> list[dict]:
    """All pending requests for one organization, oldest first."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, full_name, email, requested_role, requester_ip, "
                "created_at FROM registration_requests "
                "WHERE organization_id = %s AND status = 'pending' "
                "ORDER BY created_at ASC",
                (organization_id,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


def update_status(request_id: int, organization_id: int, status: str) -> bool:
    """Mark a request approved/rejected. Returns True if a row changed."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE registration_requests SET status = %s "
                "WHERE id = %s AND organization_id = %s",
                (status, request_id, organization_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()


def pending_email_exists(email: str) -> bool:
    """True if this email already has a pending request somewhere.

    Checked globally (not org-scoped) because `users.email` is globally
    unique -- the same email cannot end up pending in two different
    organizations and then both get approved.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM registration_requests "
                "WHERE email = %s AND status = 'pending'",
                (email,),
            )
            return cursor.fetchone() is not None
        finally:
            cursor.close()
