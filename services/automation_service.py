"""The Stage 9 automation engine: rule validation/CRUD and
`execute_automation_rules()` -- the single function, per the spec's own
design note, that every issue-creating/issue-changing route calls at the
end of its work.

Automation actions run with the *rule's own* authority, not the acting
user's: a rule was only ever created by an Admin/PM (`verify_automation_manager`),
so its actions bypass the per-user permission checks `workflow_service`
enforces for a human clicking a button (e.g. `can_update_status`) and
write directly through the repository layer instead. The user who
triggered the *event* the rule reacted to is still who the resulting
history rows/comments are attributed to (`actor_user_id`) -- there is no
synthetic "System" account in this codebase and inventing one was judged
out of scope for what this stage describes.
"""

import random

from repositories import (
    automation_repository,
    bug_history_repository,
    comment_repository,
    issue_repository,
    project_repository,
    user_repository,
)
from services import admin_service, workflow_service

TRIGGERS = ["issue_created", "status_changed", "field_updated"]
ACTION_TYPES = ["transition_status", "assign_to", "assign_to_role", "add_comment"]
CONDITION_OPERATORS = ["equals", "not_equals"]

CAN_MANAGE_AUTOMATION_ROLES = {"admin", "project_manager"}

MAX_NAME_LENGTH = 150

_COMPARATORS = {
    "equals": lambda actual, expected: str(actual) == str(expected),
    "not_equals": lambda actual, expected: str(actual) != str(expected),
}

# Placeholders `add_comment`'s text may reference -- substituted with a
# plain `str.replace`, not `str.format`, so a comment template can never
# raise on an unrelated `{...}` the author typed.
_PLACEHOLDERS = {
    "{issue_key}": lambda issue: issue["issue_key"],
    "{title}": lambda issue: issue["title"],
    "{status}": lambda issue: issue["status"],
    "{priority}": lambda issue: issue["priority"],
}


def verify_automation_manager(user_id: int) -> dict | None:
    user = user_repository.get_by_id(user_id)
    if user is None or user["role"] not in CAN_MANAGE_AUTOMATION_ROLES:
        return None
    return user


# --------------------------------------------------------------- CRUD --


def validate_rule(
    organization_id: int,
    name: str,
    project_id_raw: str,
    trigger_event: str,
    condition_fields: list[str],
    condition_operators: list[str],
    condition_values: list[str],
    action_type: str,
    action_status: str,
    action_user_id_raw: str,
    action_role: str,
    action_comment_text: str,
) -> tuple[list[str], dict]:
    """Validate a rule submitted from the "+ New Rule" form. The frontend
    only offers one action per rule (a single Action dropdown, not a
    repeatable list) even though `actions` is stored as a JSON list --
    see STAGE-09-REPORT.md for why -- so `cleaned["actions"]` always ends
    up with either zero or one entries.
    """
    errors: list[str] = []

    name = (name or "").strip()
    if not name:
        errors.append("Rule name is required.")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"Rule name must be {MAX_NAME_LENGTH} characters or fewer.")

    project_id: int | None = None
    project_id_raw = (project_id_raw or "").strip()
    if project_id_raw:
        try:
            project_id = int(project_id_raw)
        except ValueError:
            errors.append("Invalid project selection.")
            project_id = None
        if project_id is not None and project_repository.get_by_id_and_org(project_id, organization_id) is None:
            errors.append("Selected project was not found in your organization.")
            project_id = None

    if trigger_event not in TRIGGERS:
        errors.append("Select a valid trigger.")

    conditions: list[dict] = []
    for index, field in enumerate(condition_fields):
        field = (field or "").strip()
        if not field:
            continue
        operator = condition_operators[index] if index < len(condition_operators) else "equals"
        if operator not in CONDITION_OPERATORS:
            operator = "equals"
        value = condition_values[index] if index < len(condition_values) else ""
        conditions.append({"field": field, "operator": operator, "value": value})

    actions: list[dict] = []
    if action_type not in ACTION_TYPES:
        errors.append("Select a valid action.")
    elif action_type == "transition_status":
        if action_status not in workflow_service.STATUSES:
            errors.append("Select a valid target status for the action.")
        else:
            actions.append({"type": "transition_status", "status": action_status})
    elif action_type == "assign_to":
        try:
            target_user_id = int(action_user_id_raw)
        except (TypeError, ValueError):
            errors.append("Select a user to assign to.")
            target_user_id = None
        if target_user_id is not None:
            target = user_repository.get_by_id_and_org(target_user_id, organization_id)
            if target is None or target["role"] != "developer":
                errors.append("The assignee must be a developer in your organization.")
            else:
                actions.append({"type": "assign_to", "user_id": target_user_id})
    elif action_type == "assign_to_role":
        if action_role not in admin_service.ROLES:
            errors.append("Select a valid role for the action.")
        else:
            actions.append({"type": "assign_to_role", "role": action_role})
    elif action_type == "add_comment":
        text = (action_comment_text or "").strip()
        if not text:
            errors.append("Enter the comment text for the action.")
        else:
            actions.append({"type": "add_comment", "text": text})

    cleaned = {
        "name": name,
        "project_id": project_id,
        "trigger_event": trigger_event,
        "conditions": conditions,
        "actions": actions,
    }
    return errors, cleaned


def create_rule(organization_id: int, cleaned: dict) -> int:
    return automation_repository.create(
        organization_id=organization_id,
        project_id=cleaned["project_id"],
        name=cleaned["name"],
        trigger_event=cleaned["trigger_event"],
        conditions=cleaned["conditions"],
        actions=cleaned["actions"],
    )


def update_rule(rule_id: int, organization_id: int, cleaned: dict) -> bool:
    return automation_repository.update(
        rule_id=rule_id,
        organization_id=organization_id,
        project_id=cleaned["project_id"],
        name=cleaned["name"],
        trigger_event=cleaned["trigger_event"],
        conditions=cleaned["conditions"],
        actions=cleaned["actions"],
    )


def get_rule(rule_id: int, organization_id: int) -> dict | None:
    return automation_repository.get_by_id_and_org(rule_id, organization_id)


def list_rules(organization_id: int) -> list[dict]:
    return automation_repository.list_by_organization(organization_id)


def toggle_rule(rule_id: int, organization_id: int) -> tuple[bool, str | None]:
    rule = get_rule(rule_id, organization_id)
    if rule is None:
        return False, "Rule not found."
    updated = automation_repository.set_enabled(rule_id, organization_id, not rule["enabled"])
    if not updated:
        return False, "Could not update the rule."
    return True, None


def delete_rule(rule_id: int, organization_id: int) -> bool:
    return automation_repository.delete(rule_id, organization_id)


def condition_summary(rule: dict) -> str:
    if not rule["conditions"]:
        return "Always"
    parts = []
    for condition in rule["conditions"]:
        op = "=" if condition["operator"] == "equals" else "!="
        parts.append(f'{condition["field"]} {op} {condition["value"]}')
    return " AND ".join(parts)


def action_summary(rule: dict, organization_id: int) -> str:
    if not rule["actions"]:
        return "No action configured"
    action = rule["actions"][0]
    action_type = action.get("type")
    if action_type == "transition_status":
        return f'Transition status to "{action.get("status")}"'
    if action_type == "assign_to":
        target = user_repository.get_by_id_and_org(action.get("user_id"), organization_id)
        return f'Assign to {target["full_name"] if target else "(unknown user)"}'
    if action_type == "assign_to_role":
        return f'Assign to a random {admin_service.ROLE_LABELS.get(action.get("role"), action.get("role"))}'
    if action_type == "add_comment":
        text = action.get("text", "")
        return f'Add comment: "{text[:60]}{"…" if len(text) > 60 else ""}"'
    return "Unknown action"


# --------------------------------------------------------- the engine --


def _conditions_pass(conditions: list[dict], eval_context: dict) -> bool:
    for condition in conditions:
        comparator = _COMPARATORS.get(condition.get("operator"), _COMPARATORS["equals"])
        actual = eval_context.get(condition.get("field"))
        if not comparator(actual, condition.get("value")):
            return False
    return True


def _render_placeholders(text: str, issue: dict) -> str:
    for token, getter in _PLACEHOLDERS.items():
        if token in text:
            text = text.replace(token, str(getter(issue)))
    return text


def _run_transition_status(action: dict, issue: dict, actor_user_id: int, organization_id: int) -> None:
    new_status = action.get("status")
    if new_status not in workflow_service.STATUSES:
        return
    old_status = issue["status"]
    if new_status == old_status:
        return
    if not issue_repository.update_status(issue["id"], organization_id, new_status):
        return
    bug_history_repository.record(
        bug_id=issue["id"], changed_by=actor_user_id, old_status=old_status, new_status=new_status
    )
    issue["status"] = new_status


def _run_assign(new_assigned_to: int, issue: dict, actor_user_id: int, organization_id: int) -> None:
    old_assigned_to = issue["assigned_to"]
    if new_assigned_to == old_assigned_to:
        return

    old_status = issue["status"]
    new_status = "In Progress" if old_status == "To Do" else old_status

    if not issue_repository.update_assignment(issue["id"], organization_id, new_assigned_to, new_status):
        return

    bug_history_repository.record(
        bug_id=issue["id"],
        changed_by=actor_user_id,
        old_assigned_to=old_assigned_to,
        new_assigned_to=new_assigned_to,
    )
    if new_status != old_status:
        bug_history_repository.record(
            bug_id=issue["id"], changed_by=actor_user_id, old_status=old_status, new_status=new_status
        )
    issue["assigned_to"] = new_assigned_to
    issue["status"] = new_status


def _run_action(action: dict, issue: dict, actor_user_id: int, organization_id: int) -> None:
    action_type = action.get("type")

    if action_type == "transition_status":
        _run_transition_status(action, issue, actor_user_id, organization_id)

    elif action_type == "assign_to":
        target = user_repository.get_by_id_and_org(action.get("user_id"), organization_id)
        if target is not None and target["role"] == "developer":
            _run_assign(target["id"], issue, actor_user_id, organization_id)

    elif action_type == "assign_to_role":
        # "picks a real user with that role in the org, not a hardcoded
        # ID" -- the candidate pool is queried fresh every time this runs.
        candidates = [
            user for user in user_repository.list_by_organization(organization_id)
            if user["role"] == action.get("role")
        ]
        if candidates:
            _run_assign(random.choice(candidates)["id"], issue, actor_user_id, organization_id)

    elif action_type == "add_comment":
        text = _render_placeholders(action.get("text", ""), issue)
        comment_repository.create(issue["id"], actor_user_id, text)


def execute_automation_rules(
    organization_id: int, project_id: int, trigger_event: str, context: dict, actor_user_id: int
) -> None:
    """Fetch enabled rules matching the org/project/trigger, evaluate each
    rule's conditions against `context` and run matching actions in
    order -- the spec's own design note, implemented as one function so
    every calling route stays a one-line addition at the end of its
    existing work.

    `context` must include `"issue"` (the issue's current, post-change
    row) plus whatever trigger-specific keys apply (`old_status`/
    `new_status` for `status_changed`; `field_name`/`old_value`/
    `new_value` for `field_updated`). Every key is flattened together with
    the issue's own fields into one evaluation namespace, so a condition
    can reference either a plain issue column (`priority`, `issue_type`,
    `status`) or a trigger-specific key (`new_status`, `field_name`, ...)
    by the same simple `{"field": ..., "operator": ..., "value": ...}`
    shape.
    """
    issue = context.get("issue")
    if issue is None:
        return

    eval_context = dict(issue)
    eval_context.update({key: value for key, value in context.items() if key != "issue"})

    for rule in automation_repository.list_matching(organization_id, project_id, trigger_event):
        if not _conditions_pass(rule["conditions"], eval_context):
            continue
        for action in rule["actions"]:
            _run_action(action, issue, actor_user_id, organization_id)
