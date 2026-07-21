"""HTTP handlers for the Kanban board.

`GET /board` renders the page; `POST /board/move` is the drag-and-drop
endpoint, returning JSON rather than a redirect since it's called via
`fetch()` from `static/script.js`, not a plain form submission. Both
reuse Stage 6's `workflow_service` for the actual permission check and
status change -- nothing here decides who's allowed to move a card, it
only decides how the result is presented (page vs. JSON).
"""

from flask import Blueprint, jsonify, render_template, request

from services import automation_service, board_service, issue_service, project_service, workflow_service
from utils.auth import current_user, login_required

board_bp = Blueprint("board", __name__)


@board_bp.get("/board")
@login_required
def board():
    user = current_user()
    projects = project_service.list_projects(user["organization_id"])

    requested_project_id = request.args.get("project", type=int)
    project = None
    if requested_project_id is not None:
        project = project_service.get_project(requested_project_id, user["organization_id"])
    if project is None and projects:
        # No (valid) project requested -- default to the first project in
        # the organization so the board is never blank when a project
        # simply wasn't specified in the URL.
        project = projects[0]

    group_by = request.args.get("group_by", board_service.DEFAULT_GROUP_BY)
    if group_by not in board_service.GROUP_BY_OPTIONS:
        group_by = board_service.DEFAULT_GROUP_BY

    # Accepted per the spec's route table ("accepts project, sprint,
    # group_by query params") but not yet functional -- there is no sprint
    # data model until Stage 8. Passed through only so the (disabled)
    # sprint selector in the template can echo it back.
    sprint = request.args.get("sprint", "")

    board_data = None
    if project is not None:
        board_data = board_service.get_board(
            user["organization_id"], project["id"], user["id"], group_by
        )

    return render_template(
        "board.html",
        projects=projects,
        selected_project=project,
        board=board_data,
        group_by=group_by,
        group_by_options=board_service.GROUP_BY_OPTIONS,
        sprint=sprint,
    )


@board_bp.post("/board/move")
@login_required
def move_issue():
    user = current_user()
    issue_id = request.form.get("issue_id", type=int)
    new_status = request.form.get("status", "")

    if issue_id is None:
        return jsonify(ok=False, error="Invalid request."), 400

    issue = issue_service.get_issue(issue_id, user["organization_id"])
    if issue is None:
        return jsonify(ok=False, error="Issue not found."), 404

    if new_status not in board_service.BOARD_STATUSES:
        return jsonify(ok=False, error="Invalid status."), 400

    permitted_user = workflow_service.can_update_status(user["id"], issue)
    if permitted_user is None:
        return jsonify(ok=False, error="You do not have permission to change this issue's status."), 403

    old_status = issue["status"]
    ok, error = workflow_service.change_status(issue, new_status, permitted_user)
    if ok and new_status != old_status:
        # Drag-and-drop is just another way to change status -- it must
        # trigger the same `status_changed` automation the detail page's
        # status dropdown does (routes/issue_routes.py::change_status), or
        # a rule like "on Testing, notify QA" would silently never fire
        # for anyone using the board.
        updated_issue = issue_service.get_issue(issue_id, user["organization_id"])
        automation_service.execute_automation_rules(
            organization_id=user["organization_id"],
            project_id=issue["project_id"],
            trigger_event="status_changed",
            context={"issue": updated_issue, "old_status": old_status, "new_status": new_status},
            actor_user_id=permitted_user["id"],
        )
    return jsonify(ok=ok, error=error)
