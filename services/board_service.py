"""Kanban board business rules: querying, grouping, pagination and the
per-card drag permission flag.

No new tables -- per the spec, this stage is "purely a new way of querying
and displaying `bugs` data already modeled in Stage 5/6." Everything here
reads `issue_repository.list_board_issues()` (one query per board load,
per the spec's own query-design note) and reshapes the result in Python;
`workflow_service` still owns every actual status/assignment write, so
this module never mutates anything itself.
"""

from repositories import issue_repository
from services import issue_service, workflow_service

# The four columns the board shows. Deliberately excludes "Idea" -- the
# spec calls this out explicitly ("'Idea' issues are intentionally
# excluded from the board - they live in the backlog, built in Stage 8"),
# so this is NOT simply `workflow_service.STATUSES` with one entry
# dropped by accident; it is its own ordered list, kept separate from that
# module's five-status list on purpose.
BOARD_STATUSES = ["To Do", "In Progress", "Testing", "Done"]

GROUP_BY_OPTIONS = ["none", "assignee", "priority", "type"]
DEFAULT_GROUP_BY = "none"

# How many cards a column shows before a "Load more" control appears.
# Only applies when group_by is "none" -- see module docstring in
# STAGE-07-REPORT.md §5 for why pagination and grouping aren't combined.
PAGE_SIZE = 20


def get_board(organization_id: int, project_id: int, user_id: int, group_by: str) -> dict:
    """Build everything the board template needs for one project: four
    columns (each with grouped/paginated card entries) plus the list of
    distinct assignees present, for the quick-filter avatar row.
    """
    if group_by not in GROUP_BY_OPTIONS:
        group_by = DEFAULT_GROUP_BY

    issues = issue_repository.list_board_issues(organization_id, project_id)

    assignees_by_id: dict[int, str] = {}
    columns = []
    for status in BOARD_STATUSES:
        status_cards = [
            _to_card(issue, user_id) for issue in issues if issue["status"] == status
        ]
        for card in status_cards:
            if card["assigned_to"]:
                assignees_by_id[card["assigned_to"]] = card["assigned_to_name"]

        entries, hidden_count = _build_entries(status_cards, group_by)
        columns.append(
            {
                "status": status,
                "count": len(status_cards),
                "entries": entries,
                "hidden_count": hidden_count,
            }
        )

    assignees = [
        {"id": user_id_, "name": name}
        for user_id_, name in sorted(assignees_by_id.items(), key=lambda kv: kv[1].lower())
    ]

    return {"columns": columns, "assignees": assignees, "group_by": group_by}


def _to_card(issue: dict, user_id: int) -> dict:
    """One board card's display fields, plus `can_drag` -- computed with
    the exact same `workflow_service.can_update_status` rule Stage 6's
    status-change form uses, so a card is only draggable-with-effect for
    the same user it would show a status dropdown to on the detail page.
    The board still lets an unauthorized user *attempt* the drag (see
    `routes/board_routes.py::move_issue`); this flag only drives the
    card's own drag affordance in the browser.
    """
    return {
        "id": issue["id"],
        "issue_key": issue["issue_key"],
        "issue_type": issue["issue_type"],
        "title": issue["title"],
        "priority": issue["priority"],
        "status": issue["status"],
        "assigned_to": issue["assigned_to"],
        "assigned_to_name": issue["assigned_to_name"],
        "story_points": issue["story_points"],
        "labels": issue["labels"],
        "can_drag": workflow_service.can_update_status(user_id, issue) is not None,
    }


def _build_entries(cards: list[dict], group_by: str) -> tuple[list[dict], int]:
    """Turn one column's cards into a flat list of template "entries" --
    either a group-header entry or a card entry (flagged `hidden` for
    pagination) -- plus how many cards are hidden.
    """
    if group_by == "none":
        visible, hidden = cards[:PAGE_SIZE], cards[PAGE_SIZE:]
        entries = [{"kind": "card", "hidden": False, "card": c} for c in visible]
        entries += [{"kind": "card", "hidden": True, "card": c} for c in hidden]
        return entries, len(hidden)

    entries = []
    for label, group_cards in _group_cards(cards, group_by):
        entries.append({"kind": "header", "label": label})
        entries += [{"kind": "card", "hidden": False, "card": c} for c in group_cards]
    return entries, 0


def _group_cards(cards: list[dict], group_by: str) -> list[tuple[str, list[dict]]]:
    """Split cards into ordered (label, cards) groups.

    Only groups actually present among `cards` get a header -- an empty
    "Critical" group never appears just because Critical is a valid
    priority.
    """
    if group_by == "assignee":
        def key_of(card):
            return card["assigned_to_name"] or "Unassigned"

        keys = sorted(
            {key_of(c) for c in cards}, key=lambda k: (k == "Unassigned", k.lower())
        )
    elif group_by == "priority":
        # issue_service.PRIORITIES is Low -> Critical; the board wants the
        # most urgent group first.
        order = list(reversed(issue_service.PRIORITIES))

        def key_of(card):
            return card["priority"]

        keys = [p for p in order if any(key_of(c) == p for c in cards)]
    elif group_by == "type":
        order = issue_service.ISSUE_TYPES

        def key_of(card):
            return card["issue_type"]

        keys = [t for t in order if any(key_of(c) == t for c in cards)]
    else:
        return [(None, cards)]

    return [(key, [c for c in cards if key_of(c) == key]) for key in keys]
