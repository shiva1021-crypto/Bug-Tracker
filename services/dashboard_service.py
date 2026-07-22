"""Configurable dashboard: widget types, the org-default layout new users
inherit automatically and per-user customization.

Storage model (see `repositories/dashboard_widget_repository.py`'s
docstring): each organization gets one *default* layout, stored as rows
with `user_id IS NULL`, seeded once at organization creation
(`ensure_org_defaults`, called from `services/auth_service.py::register`'s
new-org path, mirroring how `project_service.create_default_project` is
already called there). A user who has never customized their own
dashboard simply sees that default layout rendered read-through, with no
personal rows of their own -- satisfying "a new user's dashboard shows the
default widget set with no manual setup" by construction, not by copying
anything at signup time.

The first time a user actually adds or removes a widget, their personal
layout is "forked" from the org default (`_ensure_personal_layout`): every
default row is copied into a personal row for that user and the
requested change is applied on top of that copy. From then on, that user
always has personal rows and reads take the personal list rather than the
org default. This is what makes "removing and re-adding a widget preserves
the rest of the layout" true even for a user's *very first* edit -- the
fork happens before the edit, not after, so the other three default
widgets survive it.
"""

from repositories import dashboard_widget_repository, issue_repository

WIDGET_TYPES = [
    "stats_summary",
    "recent_issues",
    "issues_by_status",
    "issues_by_priority",
    "issues_by_severity",
    "issues_by_type",
]

WIDGET_LABELS = {
    "stats_summary": "Statistics Summary",
    "recent_issues": "Recent Issues",
    "issues_by_status": "Issues by Status",
    "issues_by_priority": "Issues by Priority",
    "issues_by_severity": "Issues by Severity",
    "issues_by_type": "Issues by Type",
}

WIDTHS = ["full", "half", "third"]

MAX_TITLE_LENGTH = 120

# "New users get a sensible default layout automatically (e.g. Statistics
# Summary + Issues by Status + Issues by Priority + Recent Issues)" -- the
# spec's own example, used verbatim.
DEFAULT_LAYOUT = [
    {"widget_type": "stats_summary", "title": "Statistics Summary", "width": "full"},
    {"widget_type": "issues_by_status", "title": "Issues by Status", "width": "half"},
    {"widget_type": "issues_by_priority", "title": "Issues by Priority", "width": "half"},
    {"widget_type": "recent_issues", "title": "Recent Issues", "width": "full"},
]


def ensure_org_defaults(organization_id: int) -> None:
    """Seed an organization's default widget layout, once. Called from the
    new-organization registration path; idempotent (a no-op if defaults
    already exist), so it is also safe to call defensively from the
    dashboard route for any organization that predates this stage."""
    if dashboard_widget_repository.count_org_defaults(organization_id) > 0:
        return
    for position, widget in enumerate(DEFAULT_LAYOUT):
        dashboard_widget_repository.create(
            organization_id=organization_id,
            user_id=None,
            widget_type=widget["widget_type"],
            title=widget["title"],
            config=None,
            position=position,
            width=widget["width"],
        )


def get_layout(organization_id: int, user_id: int) -> list[dict]:
    """The widgets to render for this user: their personal layout if
    they've ever customized it, otherwise the organization's default."""
    personal = dashboard_widget_repository.list_for_user(organization_id, user_id)
    if personal:
        return personal
    return dashboard_widget_repository.list_org_defaults(organization_id)


def _ensure_personal_layout(organization_id: int, user_id: int) -> dict[int, int]:
    """Fork the org default into personal rows for this user, if they
    don't have any personal rows yet. A no-op (returning an empty mapping)
    for a user who has already customized their dashboard at least once.

    Returns `{default_widget_id: new_personal_widget_id}`. This matters
    because forking assigns each copied row a brand-new id -- a caller
    that received a default widget's id from a page render (e.g. "remove
    widget 7") needs this mapping to know which *personal* row that
    actually corresponds to once the fork has happened, since id 7 itself
    now belongs to an org-default row this user no longer reads from.
    """
    if dashboard_widget_repository.list_for_user(organization_id, user_id):
        return {}
    mapping: dict[int, int] = {}
    for default in dashboard_widget_repository.list_org_defaults(organization_id):
        new_id = dashboard_widget_repository.create(
            organization_id=organization_id,
            user_id=user_id,
            widget_type=default["widget_type"],
            title=default["title"],
            config=default["config"] or None,
            position=default["position"],
            width=default["width"],
        )
        mapping[default["id"]] = new_id
    return mapping


def validate_widget(widget_type: str, title: str, width: str) -> tuple[list[str], dict]:
    errors: list[str] = []

    if widget_type not in WIDGET_TYPES:
        errors.append("Select a valid widget type.")

    title = (title or "").strip() or WIDGET_LABELS.get(widget_type, "Widget")
    if len(title) > MAX_TITLE_LENGTH:
        errors.append(f"Widget title must be {MAX_TITLE_LENGTH} characters or fewer.")

    if width not in WIDTHS:
        errors.append("Select a valid widget width.")

    return errors, {"widget_type": widget_type, "title": title, "width": width}


def add_widget(organization_id: int, user_id: int, cleaned: dict) -> int:
    _ensure_personal_layout(organization_id, user_id)
    next_position = dashboard_widget_repository.max_position_for_user(organization_id, user_id) + 1
    return dashboard_widget_repository.create(
        organization_id=organization_id,
        user_id=user_id,
        widget_type=cleaned["widget_type"],
        title=cleaned["title"],
        config=None,
        position=next_position,
        width=cleaned["width"],
    )


def remove_widget(organization_id: int, user_id: int, widget_id: int) -> bool:
    """Remove one widget from this user's dashboard.

    `widget_id` is whatever id the page rendered -- which, for a user who
    has never customized their layout, is an org-*default* row's id, not a
    personal one. `_ensure_personal_layout` forks the defaults into fresh
    personal rows (with new ids) before this delete runs, so `widget_id`
    is translated through its returned mapping first; for a user who
    already had personal rows, the mapping is empty and `widget_id` is
    used as-is.
    """
    fork_mapping = _ensure_personal_layout(organization_id, user_id)
    actual_widget_id = fork_mapping.get(widget_id, widget_id)
    return dashboard_widget_repository.delete(actual_widget_id, organization_id, user_id)


# ------------------------------------------------------- widget data --


def _chart_data(rows: list[dict], label_key: str) -> dict:
    """Shared shape for every doughnut-chart widget: parallel `labels`/
    `counts` lists, ready for Chart.js."""
    return {
        "labels": [row[label_key] for row in rows],
        "counts": [row["count"] for row in rows],
    }


def widget_data(widget: dict, organization_id: int) -> dict:
    """Fetch whatever data one widget needs to render, dispatched by its
    `widget_type`. Every widget is organization-wide (no per-widget
    project filter) -- the spec's Configurable Dashboard section describes
    none, unlike the Reports page, which does."""
    widget_type = widget["widget_type"]

    if widget_type == "stats_summary":
        return issue_repository.stats_summary(organization_id)
    if widget_type == "recent_issues":
        return {"issues": issue_repository.list_recent(organization_id, limit=5)}
    if widget_type == "issues_by_status":
        return _chart_data(issue_repository.count_by_status(organization_id), "status")
    if widget_type == "issues_by_priority":
        return _chart_data(issue_repository.count_by_priority(organization_id), "priority")
    if widget_type == "issues_by_severity":
        return _chart_data(issue_repository.count_by_severity(organization_id), "severity")
    if widget_type == "issues_by_type":
        return _chart_data(issue_repository.count_by_type(organization_id), "issue_type")
    return {}
