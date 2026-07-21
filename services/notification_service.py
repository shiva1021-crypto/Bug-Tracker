"""Builds and queues notification emails.

Every function here does exactly one thing: figure out who should be
emailed and what the message should say, then write a row to
`email_outbox` via `email_outbox_repository.create()`. Nothing in this
module ever sends an email itself or touches SMTP -- that happens later,
out of the request/response cycle, in `services/notification_worker.py`.
This split is the whole point of the outbox pattern: writing a row is one
fast INSERT, so a caller (e.g. `workflow_service.change_status`) is never
blocked waiting on a mail server.
"""

from config import config
from repositories import email_outbox_repository, user_repository, watcher_repository


def _issue_url(issue: dict) -> str:
    return f"{config.APP_BASE_URL}/issues/{issue['id']}"


def notify_issue_assigned(issue: dict, assignee: dict) -> None:
    """Sent when an issue is assigned (or reassigned) to a developer.
    Never called for an *un*-assignment -- there is no one to notify."""
    subject = f"[{issue['issue_key']}] Assigned to you: {issue['title']}"
    body = (
        f"You have been assigned to {issue['issue_key']} - {issue['title']}.\n\n"
        f"View it here: {_issue_url(issue)}\n"
    )
    email_outbox_repository.create(assignee["email"], subject, body)


def notify_status_changed(issue: dict, old_status: str, new_status: str) -> None:
    """Sent to the issue's reporter and every current watcher.

    Recipients are deduplicated (a reporter who is also watching their own
    issue gets exactly one email, not two). The user who made the change
    is not excluded from this list -- the spec does not ask for that, and
    excluding "the actor" would need a notion of "who is watching notified
    of their own action" this stage doesn't otherwise track; flagged in
    STAGE-10-REPORT.md.
    """
    recipients: dict[str, str] = {}  # email -> full_name, for dedup

    reporter = user_repository.get_by_id(issue["reporter_id"])
    if reporter:
        recipients[reporter["email"]] = reporter["full_name"]

    for watcher in watcher_repository.list_watcher_users(issue["id"]):
        recipients[watcher["email"]] = watcher["full_name"]

    if not recipients:
        return

    subject = f"[{issue['issue_key']}] Status changed: {old_status} → {new_status}"
    body = (
        f"{issue['issue_key']} - {issue['title']} changed status from "
        f"{old_status} to {new_status}.\n\n"
        f"View it here: {_issue_url(issue)}\n"
    )
    for email in recipients:
        email_outbox_repository.create(email, subject, body)


def notify_registration_approved(email: str, full_name: str, organization_name: str) -> None:
    subject = f"Your request to join {organization_name} was approved"
    body = (
        f"Hi {full_name},\n\n"
        f"Your request to join {organization_name} on Bug Tracker has been approved. "
        f"You can now log in: {config.APP_BASE_URL}/login\n"
    )
    email_outbox_repository.create(email, subject, body)


def notify_registration_rejected(email: str, full_name: str, organization_name: str) -> None:
    subject = f"Your request to join {organization_name} was declined"
    body = (
        f"Hi {full_name},\n\n"
        f"Your request to join {organization_name} on Bug Tracker was declined by "
        "an administrator. If you believe this is a mistake, contact your "
        "organization's admin directly.\n"
    )
    email_outbox_repository.create(email, subject, body)
