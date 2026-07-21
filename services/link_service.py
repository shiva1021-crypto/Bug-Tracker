"""Issue-linking business rules: creating a typed, directional link between
two issues, listing them with the correct per-side label, and removing one
from either side.

Per the spec, a link is stored once (`bug_id_a` -> `bug_id_b` with a
type) and the *reverse* label is derived, not stored, when the other
issue's page renders it -- there is deliberately no second database row.
"""

from repositories import issue_link_repository, issue_repository

FORWARD_LABELS = {
    "blocks": "Blocks",
    "relates_to": "Relates to",
    "duplicates": "Duplicates",
    "clones": "Clones",
}

# Symmetric: "relates_to" reads the same from either side. The other three
# get a distinct reverse label from what was actually stored.
REVERSE_LABELS = {
    "blocks": "Blocked by",
    "relates_to": "Relates to",
    "duplicates": "Duplicated by",
    "clones": "Cloned by",
}

# What the add-link form's single <select> offers, from the *current*
# issue's point of view -- both directions of each directional type, plus
# the one symmetric type. `a_is_current` decides which side of the stored
# row the current issue ends up on: choosing "Blocked by" on WEB-5 for
# target WEB-9 stores (bug_id_a=WEB-9, bug_id_b=WEB-5, link_type=blocks),
# so WEB-9's page then correctly shows "Blocks WEB-5" via FORWARD_LABELS.
LINK_FORM_OPTIONS = [
    ("blocks_forward", "Blocks", True, "blocks"),
    ("blocks_reverse", "Blocked by", False, "blocks"),
    ("relates_to", "Relates to", True, "relates_to"),
    ("duplicates_forward", "Duplicates", True, "duplicates"),
    ("duplicates_reverse", "Duplicated by", False, "duplicates"),
    ("clones_forward", "Clones", True, "clones"),
    ("clones_reverse", "Cloned by", False, "clones"),
]

_OPTIONS_BY_VALUE = {value: (label, a_is_current, link_type) for value, label, a_is_current, link_type in LINK_FORM_OPTIONS}


def create_link(
    organization_id: int, source_issue: dict, form_value: str, target_key_raw: str
) -> tuple[bool, str | None]:
    option = _OPTIONS_BY_VALUE.get(form_value)
    if option is None:
        return False, "Select a valid link type."
    _, a_is_current, link_type = option

    target_key = (target_key_raw or "").strip().upper()
    if not target_key:
        return False, "Enter the target issue's key."

    target_issue = issue_repository.get_by_key_and_org(target_key, organization_id)
    if target_issue is None:
        return False, f'Issue "{target_key}" was not found in your organization.'
    if target_issue["id"] == source_issue["id"]:
        return False, "An issue cannot be linked to itself."

    if a_is_current:
        bug_id_a, bug_id_b = source_issue["id"], target_issue["id"]
    else:
        bug_id_a, bug_id_b = target_issue["id"], source_issue["id"]

    if _is_duplicate(bug_id_a, bug_id_b, link_type):
        return False, "That link already exists."

    issue_link_repository.create(bug_id_a, bug_id_b, link_type)
    return True, None


def _is_duplicate(bug_id_a: int, bug_id_b: int, link_type: str) -> bool:
    if issue_link_repository.exists(bug_id_a, bug_id_b, link_type):
        return True
    if link_type == "relates_to":
        # Symmetric: (B, A, relates_to) is the same relationship as
        # (A, B, relates_to), even though only one direction is ever
        # actually stored for any given pair.
        return issue_link_repository.exists(bug_id_b, bug_id_a, link_type)
    return False


def list_links(issue_id: int, organization_id: int) -> list[dict]:
    """Every link involving this issue, each with the label worded
    correctly *for this issue's side* -- "Blocks WEB-12" if this issue is
    `bug_id_a` of a `blocks` row, "Blocked by WEB-12" if it's `bug_id_b` of
    that same row."""
    rows = issue_link_repository.list_for_issue(issue_id, organization_id)
    links = []
    for row in rows:
        if row["bug_id_a"] == issue_id:
            other_id, other_key, other_title = row["bug_id_b"], row["b_issue_key"], row["b_title"]
            label = FORWARD_LABELS[row["link_type"]]
        else:
            other_id, other_key, other_title = row["bug_id_a"], row["a_issue_key"], row["a_title"]
            label = REVERSE_LABELS[row["link_type"]]
        links.append(
            {
                "id": row["id"],
                "label": label,
                "other_issue_id": other_id,
                "other_issue_key": other_key,
                "other_issue_title": other_title,
            }
        )
    return links


def remove_link(link_id: int, issue_id: int, organization_id: int) -> tuple[bool, str | None]:
    """Remove a link. Works from either linked issue's page -- `issue_id`
    just has to be one of the two participants, not specifically
    `bug_id_a`."""
    link = issue_link_repository.get_by_id_and_org(link_id, organization_id)
    if link is None:
        return False, "Link not found."
    if link["bug_id_a"] != issue_id and link["bug_id_b"] != issue_id:
        return False, "That link does not belong to this issue."

    removed = issue_link_repository.delete(link_id)
    if not removed:
        return False, "Could not remove the link."
    return True, None
