"""SQL access for the `bugs` table.

Every issue -- Epic, Story, Task, Bug, or Subtask -- lives in this one
table, per the spec ("this is the single 'issue' table"). All direct
database access for issues lives here. Services call these functions;
routes never do. Every query is scoped by organization_id, the tenant
isolation boundary from Stage 3.
"""

from repositories import project_repository
from utils.db import get_connection

_COLUMNS = (
    "id, organization_id, project_id, issue_key, issue_type, parent_id, "
    "title, description, reproduction_steps, category, priority, severity, "
    "status, reporter_id, assigned_to, screenshot_path, labels, "
    "story_points, due_date, sprint_id, created_at, updated_at"
)


def get_by_id_and_org(issue_id: int, organization_id: int) -> dict | None:
    """Return the raw issue row, or None. Used for permission/hierarchy
    checks that only need the core columns."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"SELECT {_COLUMNS} FROM bugs WHERE id = %s AND organization_id = %s",
                (issue_id, organization_id),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def get_detail_by_id_and_org(issue_id: int, organization_id: int) -> dict | None:
    """Same row, plus display-only joined fields for the detail page:
    project key/name, reporter's name, and the parent's key/title (if any)."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT b.*,
                       p.project_key   AS project_key,
                       p.name          AS project_name,
                       u.full_name     AS reporter_name,
                       assignee.full_name AS assigned_to_name,
                       parent.issue_key AS parent_issue_key,
                       parent.title     AS parent_title
                FROM bugs b
                JOIN projects p ON p.id = b.project_id
                JOIN users u ON u.id = b.reporter_id
                LEFT JOIN users assignee ON assignee.id = b.assigned_to
                LEFT JOIN bugs parent ON parent.id = b.parent_id
                WHERE b.id = %s AND b.organization_id = %s
                """,
                (issue_id, organization_id),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def list_children(parent_id: int, organization_id: int) -> list[dict]:
    """Direct children of one issue, for the detail page's sidebar list."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, issue_key, title, issue_type, status FROM bugs "
                "WHERE parent_id = %s AND organization_id = %s ORDER BY created_at ASC",
                (parent_id, organization_id),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


def list_by_project(project_id: int, organization_id: int) -> list[dict]:
    """Every issue in one project -- shown on the project detail page,
    which is the only place issues can currently be browsed from (there is
    no board yet)."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, issue_key, title, issue_type, status, priority FROM bugs "
                "WHERE project_id = %s AND organization_id = %s ORDER BY created_at ASC",
                (project_id, organization_id),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


def list_by_organization(organization_id: int) -> list[dict]:
    """Every issue in the org, light columns only -- used to build the
    Add-issue page's client-side parent-candidate list (filtered by
    project + issue type in the browser as those two fields change)."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, issue_key, title, issue_type, project_id FROM bugs "
                "WHERE organization_id = %s ORDER BY created_at ASC",
                (organization_id,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


def create(
    organization_id: int,
    project_id: int,
    project_key: str,
    issue_type: str,
    parent_id: int | None,
    title: str,
    description: str,
    reproduction_steps: str | None,
    category: str,
    priority: str,
    severity: str,
    status: str,
    reporter_id: int,
    screenshot_path: str | None,
    labels: str | None,
    story_points: int | None,
    due_date,
) -> tuple[int, str] | None:
    """Insert a new issue with a concurrency-safe, gap-free key.

    Allocates the project's next issue number and inserts the issue row in
    the SAME transaction -- exactly the concurrency rule the Stage 4 spec
    called for -- via `project_repository.allocate_next_issue_number()`,
    which takes this connection and locks the project's row with
    `SELECT ... FOR UPDATE` before either of us commits. Returns
    `(issue_id, issue_key)`, or None if the project no longer exists in
    this organization (defensive; the route layer validates this first).
    """
    with get_connection() as conn:
        try:
            next_number = project_repository.allocate_next_issue_number(
                conn, project_id, organization_id
            )
            if next_number is None:
                conn.rollback()
                return None

            issue_key = f"{project_key}-{next_number}"
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO bugs ("
                    "  organization_id, project_id, issue_key, issue_type, parent_id,"
                    "  title, description, reproduction_steps, category, priority,"
                    "  severity, status, reporter_id, screenshot_path, labels,"
                    "  story_points, due_date"
                    ") VALUES ("
                    "  %s, %s, %s, %s, %s,"
                    "  %s, %s, %s, %s, %s,"
                    "  %s, %s, %s, %s, %s,"
                    "  %s, %s"
                    ")",
                    (
                        organization_id, project_id, issue_key, issue_type, parent_id,
                        title, description, reproduction_steps, category, priority,
                        severity, status, reporter_id, screenshot_path, labels,
                        story_points, due_date,
                    ),
                )
                issue_id = cursor.lastrowid
                conn.commit()
                return issue_id, issue_key
            finally:
                cursor.close()
        except Exception:
            conn.rollback()
            raise


def update(
    issue_id: int,
    organization_id: int,
    parent_id: int | None,
    title: str,
    description: str,
    reproduction_steps: str | None,
    category: str,
    priority: str,
    severity: str,
    screenshot_path: str | None,
    labels: str | None,
    story_points: int | None,
    due_date,
) -> bool:
    """Update the editable fields of an issue.

    `project_id` and `issue_type` are deliberately not parameters here --
    see services/issue_service.py for why they are treated as immutable
    after creation. `updated_at` refreshes automatically
    (`ON UPDATE CURRENT_TIMESTAMP`).
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE bugs SET "
                "  parent_id = %s, title = %s, description = %s,"
                "  reproduction_steps = %s, category = %s, priority = %s,"
                "  severity = %s, screenshot_path = %s, labels = %s,"
                "  story_points = %s, due_date = %s "
                "WHERE id = %s AND organization_id = %s",
                (
                    parent_id, title, description, reproduction_steps, category,
                    priority, severity, screenshot_path, labels, story_points,
                    due_date, issue_id, organization_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()


def list_board_issues(organization_id: int, project_id: int) -> list[dict]:
    """Every non-"Idea" issue in one project, for the Kanban board.

    Per the Stage 7 spec's own query-design note: fetch every board-relevant
    row in a single query and let the caller (services/board_service.py)
    group them into columns/sub-groups in application code, rather than
    running one query per column -- simpler, and avoids column-count
    mismatches if a status changes mid-request. "Idea" issues are excluded
    at the SQL level since they can never appear on the board at all (they
    live in the Stage 8 backlog).
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT b.id, b.issue_key, b.issue_type, b.title, b.priority,
                       b.severity, b.status, b.assigned_to, b.story_points,
                       b.labels, b.created_at,
                       assignee.full_name AS assigned_to_name
                FROM bugs b
                LEFT JOIN users assignee ON assignee.id = b.assigned_to
                WHERE b.organization_id = %s AND b.project_id = %s
                  AND b.status <> 'Idea'
                ORDER BY b.created_at ASC
                """,
                (organization_id, project_id),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


def update_status(issue_id: int, organization_id: int, new_status: str) -> bool:
    """Update only the status column. `updated_at` refreshes automatically."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE bugs SET status = %s WHERE id = %s AND organization_id = %s",
                (new_status, issue_id, organization_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()


def update_assignment(
    issue_id: int, organization_id: int, assigned_to: int | None, status: str
) -> bool:
    """Update assignment, and (per the auto-transition rule) status in the
    same statement -- caller decides the new status; this just persists both
    atomically in one UPDATE so they can never be out of sync."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE bugs SET assigned_to = %s, status = %s "
                "WHERE id = %s AND organization_id = %s",
                (assigned_to, status, issue_id, organization_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()


def get_by_key_and_org(issue_key: str, organization_id: int) -> dict | None:
    """Look up an issue by its human-facing key (e.g. "WEB-12"), scoped to
    one organization. Used by Stage 8's issue-linking form, which lets a
    user type a target issue's key rather than pick from a list."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                f"SELECT {_COLUMNS} FROM bugs WHERE issue_key = %s AND organization_id = %s",
                (issue_key, organization_id),
            )
            return cursor.fetchone()
        finally:
            cursor.close()


def list_backlog_issues(organization_id: int, project_id: int) -> list[dict]:
    """Every issue in one project not yet assigned to a sprint -- the
    Stage 8 backlog. Unlike the Stage 7 board, this is not restricted to
    any particular status: backlog grooming happens before an issue is
    anywhere near "Done", so every status (including "Idea") belongs
    here."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id, issue_key, issue_type, title, status, priority, story_points
                FROM bugs
                WHERE organization_id = %s AND project_id = %s AND sprint_id IS NULL
                ORDER BY created_at ASC
                """,
                (organization_id, project_id),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


def list_by_sprint(sprint_id: int, organization_id: int) -> list[dict]:
    """Every issue currently assigned to one sprint -- used to render a
    sprint's section on the backlog page and to compute its burndown."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id, issue_key, issue_type, title, status, priority, story_points
                FROM bugs
                WHERE organization_id = %s AND sprint_id = %s
                ORDER BY created_at ASC
                """,
                (organization_id, sprint_id),
            )
            return cursor.fetchall()
        finally:
            cursor.close()


def update_sprint(issue_id: int, organization_id: int, sprint_id: int | None) -> bool:
    """Move an issue into a sprint, or back to the backlog (`sprint_id=None`)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE bugs SET sprint_id = %s WHERE id = %s AND organization_id = %s",
                (sprint_id, issue_id, organization_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()


def search_issues(organization_id: int, filters: dict) -> list[dict]:
    """The Stage 8 issue list/search page's query.

    `filters` may contain any of `project_id`, `status`, `priority`,
    `assigned_to`, `issue_type` -- each present key adds one `AND column =
    %s` clause; an absent key means "don't filter on this dimension at
    all". `assigned_to` also accepts the literal string `"unassigned"`,
    translated to `IS NULL` rather than an equality comparison. Built this
    way (conditions/params assembled in Python, still fully parameterized)
    rather than as several near-duplicate queries, since the whole point
    of a filter page is that any subset of these can be combined.
    """
    conditions = ["b.organization_id = %s"]
    params: list = [organization_id]

    if filters.get("project_id"):
        conditions.append("b.project_id = %s")
        params.append(filters["project_id"])
    if filters.get("status"):
        conditions.append("b.status = %s")
        params.append(filters["status"])
    if filters.get("priority"):
        conditions.append("b.priority = %s")
        params.append(filters["priority"])
    if filters.get("issue_type"):
        conditions.append("b.issue_type = %s")
        params.append(filters["issue_type"])
    if filters.get("assigned_to"):
        if filters["assigned_to"] == "unassigned":
            conditions.append("b.assigned_to IS NULL")
        else:
            conditions.append("b.assigned_to = %s")
            params.append(filters["assigned_to"])

    query = (
        "SELECT b.id, b.issue_key, b.issue_type, b.title, b.status, b.priority, "
        "       b.story_points, p.project_key AS project_key, "
        "       assignee.full_name AS assigned_to_name "
        "FROM bugs b "
        "JOIN projects p ON p.id = b.project_id "
        "LEFT JOIN users assignee ON assignee.id = b.assigned_to "
        "WHERE " + " AND ".join(conditions) + " "
        "ORDER BY b.created_at DESC"
    )

    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(query, tuple(params))
            return cursor.fetchall()
        finally:
            cursor.close()
