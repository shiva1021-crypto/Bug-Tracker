"""Issue list/search filtering: parsing query params into a filter dict,
running the search and saving/listing a user's saved filter shortcuts.

`filter_data` (what gets saved) is exactly the parsed filter dict -- "the
full query-param state," per the spec -- so re-applying a saved filter
later is just re-running `search()` with the same dict, which naturally
picks up any issue created since it was saved (see
`routes/filter_routes.py` and the Definition of Done's "including after
new issues have been added").
"""

from repositories import issue_repository, saved_filter_repository

# Every dimension the issue list page can filter on. Kept as an explicit
# allow-list so an unrecognized query-string key is silently ignored
# rather than accidentally reaching the SQL layer.
FILTER_KEYS = ("project_id", "status", "priority", "assigned_to", "issue_type")

MAX_FILTER_NAME_LENGTH = 120


def parse_filters(args) -> dict:
    """Build a filter dict from a query-param-like mapping (Flask's
    `request.args`, or a saved filter's own `filter_data` re-read back
    in). Only keys with a real value are included -- an absent key means
    "don't filter on this dimension," not "filter for an empty string."
    """
    filters: dict = {}

    project_id_raw = str(args.get("project_id") or "").strip()
    if project_id_raw:
        try:
            filters["project_id"] = int(project_id_raw)
        except ValueError:
            pass

    for key in ("status", "priority", "issue_type"):
        value = str(args.get(key) or "").strip()
        if value:
            filters[key] = value

    assigned_to_raw = str(args.get("assigned_to") or "").strip()
    if assigned_to_raw:
        if assigned_to_raw == "unassigned":
            filters["assigned_to"] = "unassigned"
        else:
            try:
                filters["assigned_to"] = int(assigned_to_raw)
            except ValueError:
                pass

    return filters


def search(organization_id: int, filters: dict) -> list[dict]:
    return issue_repository.search_issues(organization_id, filters)


def save_filter(
    user_id: int, organization_id: int, name: str, filters: dict
) -> tuple[bool, str | None]:
    name = (name or "").strip()
    if not name:
        return False, "Enter a name for this filter."
    if len(name) > MAX_FILTER_NAME_LENGTH:
        return False, f"Filter name must be {MAX_FILTER_NAME_LENGTH} characters or fewer."

    saved_filter_repository.create(user_id, organization_id, name, filters)
    return True, None


def list_saved_filters(user_id: int, organization_id: int) -> list[dict]:
    return saved_filter_repository.list_by_user(user_id, organization_id)
