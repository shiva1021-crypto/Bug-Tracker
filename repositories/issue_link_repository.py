"""SQL access for the `issue_links` table.

The link is stored once, A -> B with a type (per the spec: "derive the
reverse label for display on B's page ... rather than storing two rows").
Every read joins back through `bugs` on both sides so organization
membership can be checked without a separate query and so a link is
never returned or removable via an issue id from a different
organization.
"""

from utils.db import get_connection


def create(bug_id_a: int, bug_id_b: int, link_type: str) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO issue_links (bug_id_a, bug_id_b, link_type) VALUES (%s, %s, %s)",
                (bug_id_a, bug_id_b, link_type),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()


def exists(bug_id_a: int, bug_id_b: int, link_type: str) -> bool:
    """True if this exact (a, b, type) row already exists. Symmetric
    dedup (for `relates_to`, where (A,B) and (B,A) mean the same thing) is
    the caller's job -- see `services/link_service.py` -- this only checks
    the one direction given."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM issue_links WHERE bug_id_a = %s AND bug_id_b = %s AND link_type = %s",
                (bug_id_a, bug_id_b, link_type),
            )
            return cursor.fetchone() is not None
        finally:
            cursor.close()


def get_by_id_and_org(link_id: int, organization_id: int) -> dict | None:
    """Return a link only if both of its issues belong to this
    organization (they always should, since `create` is only ever called
    after both are looked up in-org, but this is checked again here rather
    than trusted)."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT l.id, l.bug_id_a, l.bug_id_b, l.link_type
                FROM issue_links l
                JOIN bugs a ON a.id = l.bug_id_a
                JOIN bugs b ON b.id = l.bug_id_b
                WHERE l.id = %s AND a.organization_id = %s AND b.organization_id = %s
                """,
                (link_id, organization_id, organization_id),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def list_for_issue(issue_id: int, organization_id: int) -> list[dict]:
    """Every link involving one issue, with both sides' key/title joined
    in so the service layer can compute the correct directional label
    without a second round-trip per link."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT l.id, l.bug_id_a, l.bug_id_b, l.link_type,
                       a.issue_key AS a_issue_key, a.title AS a_title,
                       b.issue_key AS b_issue_key, b.title AS b_title
                FROM issue_links l
                JOIN bugs a ON a.id = l.bug_id_a
                JOIN bugs b ON b.id = l.bug_id_b
                WHERE (l.bug_id_a = %s OR l.bug_id_b = %s)
                  AND a.organization_id = %s AND b.organization_id = %s
                ORDER BY l.id ASC
                """,
                (issue_id, issue_id, organization_id, organization_id),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


def delete(link_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM issue_links WHERE id = %s", (link_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
