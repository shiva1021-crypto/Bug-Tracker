"""Reports: date/status/priority/project filtering, chart aggregation and
CSV export.

`issue_repository.search_for_report()` is called exactly once per request
(GET /reports or GET /reports/export.csv) and every chart's counts, plus
the CSV export, are all derived from that same in-memory row list -- the
same "fetch once, group in application code" shape Stage 7's board query
established, chosen here for the same reason: the charts and the export
must always agree on which rows matched the filter and computing three
separate `GROUP BY` queries plus a fourth row-fetch could theoretically
disagree if data changed between queries.
"""

import csv
import io
from collections import Counter
from datetime import datetime

from repositories import issue_repository, user_repository
from utils.csv_safety import neutralize

CAN_VIEW_REPORTS_ROLES = {"admin", "project_manager"}

CSV_HEADER = [
    "Issue Key", "Title", "Type", "Status", "Priority", "Severity",
    "Category", "Project", "Assignee", "Reporter", "Created At",
]


def verify_report_viewer(user_id: int):
    from repositories import user_repository

    user = user_repository.get_by_id(user_id)
    if user is None or user["role"] not in CAN_VIEW_REPORTS_ROLES:
        return None
    return user


def parse_filters(args) -> tuple[list[str], dict]:
    """Parse the Reports page's filter bar query params. Returns
    `(errors, filters)`; `filters` only contains keys for dimensions that
    were actually supplied and valid."""
    errors: list[str] = []
    filters: dict = {}

    project_id = args.get("project_id", type=int)
    if project_id:
        filters["project_id"] = project_id

    status = (args.get("status") or "").strip()
    if status:
        filters["status"] = status

    priority = (args.get("priority") or "").strip()
    if priority:
        filters["priority"] = priority

    date_from_raw = (args.get("date_from") or "").strip()
    if date_from_raw:
        try:
            filters["date_from"] = datetime.strptime(date_from_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Enter a valid start date.")

    date_to_raw = (args.get("date_to") or "").strip()
    if date_to_raw:
        try:
            filters["date_to"] = datetime.strptime(date_to_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append("Enter a valid end date.")

    return errors, filters


def run_report(organization_id: int, filters: dict) -> dict:
    """Fetch the filtered issue list once and derive every chart's counts
    from it. Returns a dict with the raw `rows` (for the CSV export) plus
    `status_counts` / `priority_counts` / `category_counts`, each a list
    of `{"label": ..., "count": ...}` sorted by count descending so the
    biggest bar/slice renders first."""
    rows = issue_repository.search_for_report(organization_id, filters)

    def _breakdown(key: str) -> list[dict]:
        counts = Counter(row[key] for row in rows)
        return [
            {"label": label, "count": count}
            for label, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        ]

    return {
        "rows": rows,
        "status_counts": _breakdown("status"),
        "priority_counts": _breakdown("priority"),
        "category_counts": _breakdown("category"),
    }


def rows_to_csv(rows: list[dict]) -> str:
    """Render filtered issue rows as CSV text, safe against formula
    injection: every field is passed through `neutralize()` before being
    written, per the spec's explicit Definition of Done requirement (a
    title like `=cmd|'/c calc'!A1` must open as plain text, not execute).
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)
    for row in rows:
        writer.writerow([
            neutralize(row["issue_key"]),
            neutralize(row["title"]),
            neutralize(row["issue_type"]),
            neutralize(row["status"]),
            neutralize(row["priority"]),
            neutralize(row["severity"]),
            neutralize(row["category"]),
            neutralize(row["project_key"]),
            neutralize(row["assigned_to_name"] or "Unassigned"),
            neutralize(row["reporter_name"]),
            neutralize(row["created_at"].strftime("%Y-%m-%d %H:%M") if row["created_at"] else ""),
        ])
    return buffer.getvalue()
