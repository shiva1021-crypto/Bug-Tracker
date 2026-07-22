"""Seed realistic dummy data for manual testing.

Creates one demo organization with a user for every role (admin, project
manager, developer x2, tester x2), two projects each with sprints and
versions and roughly twenty issues spread across every type, status,
priority and severity -- plus a few comments, watchers and time entries
-- so the Kanban board, backlog, dashboard and reports all have something
real to show immediately after running this.

Run from the project root, after the schema exists:
    python -m scripts.create_tables
    python -m scripts.seed_dummy_data

Goes through the same repositories/services the app itself uses (never
raw duplicate SQL), so this data is exactly as valid as anything the UI
would produce: passwords are hashed with the same `generate_password_hash`
call `services/auth_service.py` uses, issue keys are allocated through
`project_repository.allocate_next_issue_number` (the same concurrency-safe
path issue creation always takes) and the seeded organization's dashboard
defaults are seeded via `services/dashboard_service.ensure_org_defaults`,
identical to what happens when a real organization registers.

Not idempotent and deliberately so: there is no "already seeded" column
on any of these tables to check against short of the organization's name.
Running this twice is refused outright (see `main()`) rather than silently
doubling every row -- if you want a fresh copy, delete the demo
organization's rows yourself (cascading deletes will take projects/issues/
etc. with it) or drop and recreate the database first.
"""

import sys
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from repositories import (
    comment_repository,
    issue_repository,
    organization_repository,
    project_repository,
    sprint_repository,
    time_entry_repository,
    user_repository,
    version_repository,
    watcher_repository,
)
from services import dashboard_service

ORG_NAME = "Nimbus Robotics"
DUMMY_PASSWORD = "DummyPass123!"

# (full_name, email, role, key) -- `key` is just this script's own handle
# for referring back to a user's id below, not stored anywhere.
USERS = [
    ("Ava Admin", "admin@nimbus.test", "admin", "admin"),
    ("Priya Patel", "pm@nimbus.test", "project_manager", "pm"),
    ("Derek Chen", "dev1@nimbus.test", "developer", "dev1"),
    ("Sofia Alvarez", "dev2@nimbus.test", "developer", "dev2"),
    ("Tomas Reyes", "tester1@nimbus.test", "tester", "tester1"),
    ("Grace Kim", "tester2@nimbus.test", "tester", "tester2"),
]

TODAY = date.today()


def _d(offset_days: int) -> date:
    """A date `offset_days` from today -- negative for the past."""
    return TODAY + timedelta(days=offset_days)


def create_org_and_users() -> tuple[int, dict]:
    org_id = organization_repository.create(ORG_NAME)
    password_hash = generate_password_hash(DUMMY_PASSWORD)
    user_ids = {}
    for full_name, email, role, key in USERS:
        user_ids[key] = user_repository.create(
            full_name=full_name,
            email=email,
            password_hash=password_hash,
            organization_id=org_id,
            role=role,
        )
    return org_id, user_ids


def create_project_with_sprints_and_versions(org_id: int, name: str, project_key: str) -> dict:
    """One project plus its three sprints (closed/active/future) and two
    versions (released/unreleased). Returns a dict of everything the issue
    -building step below needs to refer back to."""
    project_id = project_repository.create(org_id, name, project_key, f"{name} -- demo project.")

    closed_sprint_id = sprint_repository.create(
        org_id, project_id, "Sprint 1", "Initial groundwork.", _d(-28), _d(-15),
    )
    sprint_repository.set_status(closed_sprint_id, org_id, "closed")

    active_sprint_id = sprint_repository.create(
        org_id, project_id, "Sprint 2", "Current sprint in progress.", _d(-14), _d(0),
    )
    sprint_repository.set_status(active_sprint_id, org_id, "active")

    future_sprint_id = sprint_repository.create(
        org_id, project_id, "Sprint 3", "Planned next.", _d(1), _d(14),
    )
    # sprints default to 'future' -- no set_status call needed.

    released_version_id = version_repository.create(
        org_id, project_id, "v1.0", "First public release.", _d(-20),
    )
    version_repository.set_status(released_version_id, org_id, "released")

    unreleased_version_id = version_repository.create(
        org_id, project_id, "v1.1", "Next release, in progress.",
    )
    # versions default to 'unreleased' -- no set_status call needed.

    return {
        "id": project_id,
        "key": project_key,
        "sprints": {"closed": closed_sprint_id, "active": active_sprint_id, "future": future_sprint_id},
        "versions": {"released": released_version_id, "unreleased": unreleased_version_id},
    }


def create_issue(org_id: int, project: dict, spec: dict, users: dict) -> tuple[int, str]:
    """Create one issue per `spec`, then apply whatever assignment/sprint/
    status changes it asks for on top of the freshly-created row (issue
    creation itself never accepts assigned_to or sprint_id -- those are
    always separate, later calls in the real app too)."""
    result = issue_repository.create(
        organization_id=org_id,
        project_id=project["id"],
        project_key=project["key"],
        issue_type=spec["type"],
        parent_id=spec.get("parent_id"),
        title=spec["title"],
        description=spec["description"],
        reproduction_steps=spec.get("reproduction_steps"),
        category=spec.get("category", "General"),
        priority=spec.get("priority", "Medium"),
        severity=spec.get("severity", "Minor"),
        status="Idea",
        reporter_id=users[spec["reporter"]],
        screenshot_path=None,
        labels=spec.get("labels"),
        story_points=spec.get("story_points"),
        due_date=spec.get("due_date"),
        fix_version_id=project["versions"].get(spec["fix_version"]) if spec.get("fix_version") else None,
    )
    issue_id, issue_key = result

    final_status = spec.get("status", "Idea")
    assignee_key = spec.get("assignee")
    if assignee_key or final_status != "Idea":
        issue_repository.update_assignment(
            issue_id, org_id,
            users[assignee_key] if assignee_key else None,
            final_status,
        )

    sprint_key = spec.get("sprint")
    if sprint_key:
        issue_repository.update_sprint(issue_id, org_id, project["sprints"][sprint_key])

    for commenter_key, text in spec.get("comments", []):
        comment_repository.create(issue_id, users[commenter_key], text)

    for watcher_key in spec.get("watchers", []):
        watcher_repository.add(issue_id, users[watcher_key])

    for logger_key, hours, note in spec.get("time_entries", []):
        time_entry_repository.create(issue_id, users[logger_key], hours, note)

    return issue_id, issue_key


def seed_web_project(org_id: int, project: dict, users: dict) -> int:
    count = 0

    epic_id, _ = create_issue(org_id, project, {
        "type": "Epic", "title": "Checkout Revamp",
        "description": "Redesign the checkout flow to reduce cart abandonment.",
        "priority": "High", "severity": "Major", "status": "In Progress",
        "reporter": "pm", "assignee": "dev1", "category": "Checkout",
    }, users)
    count += 1

    story_id, _ = create_issue(org_id, project, {
        "type": "Story", "parent_id": epic_id,
        "title": "Add saved payment methods",
        "description": "As a customer, I want to save a card so I can check out faster next time.",
        "priority": "High", "severity": "Major", "status": "In Progress",
        "reporter": "pm", "assignee": "dev1", "category": "Checkout",
        "story_points": 5, "sprint": "active",
        "watchers": ["pm", "tester1"],
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Subtask", "parent_id": story_id,
        "title": "Build payment method API",
        "description": "CRUD endpoints for a customer's saved payment methods.",
        "priority": "High", "status": "Done",
        "reporter": "dev1", "assignee": "dev1", "category": "Checkout",
        "sprint": "closed",
        "time_entries": [("dev1", 6.5, "API implementation + tests")],
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Subtask", "parent_id": story_id,
        "title": "Payment method UI",
        "description": "Add/remove saved cards screen in account settings.",
        "priority": "Medium", "status": "To Do",
        "reporter": "dev1", "assignee": "dev2", "category": "Checkout",
        "sprint": "active",
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Task", "parent_id": epic_id,
        "title": "Update pricing page copy",
        "description": "Reflect the new checkout flow in the marketing pricing page.",
        "priority": "Low", "reporter": "pm", "category": "Marketing",
        "due_date": _d(10),
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Story",
        "title": "Guest checkout flow",
        "description": "Allow checkout without creating an account.",
        "priority": "Medium", "severity": "Major", "status": "To Do",
        "reporter": "pm", "assignee": "dev2", "category": "Checkout",
        "story_points": 8, "sprint": "future",
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Bug",
        "title": "Cart total miscalculates with coupon applied",
        "description": "Applying a percentage-off coupon rounds the total incorrectly, undercharging by a few cents.",
        "reproduction_steps": "1. Add two items to cart\n2. Apply coupon SAVE10\n3. Compare displayed total to manual calculation",
        "priority": "Critical", "severity": "Blocker", "status": "Testing",
        "reporter": "tester1", "assignee": "dev2", "category": "Checkout",
        "sprint": "active", "due_date": _d(2),
        "comments": [
            ("tester1", "Confirmed on both Chrome and Firefox, always off by rounding on the tax line."),
            ("dev2", "Found it -- we're rounding before applying tax instead of after. Fix incoming."),
        ],
        "watchers": ["pm", "tester1"],
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Bug",
        "title": "Checkout button unresponsive on Safari",
        "description": "The 'Place Order' button does not respond to clicks in Safari 17 on macOS.",
        "reproduction_steps": "1. Open checkout in Safari\n2. Fill in all fields\n3. Click Place Order",
        "priority": "High", "severity": "Major", "status": "To Do",
        "reporter": "tester2", "category": "Checkout",
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Bug",
        "title": "Currency symbol wrong for EUR customers",
        "description": "European customers see a '$' prefix instead of '€' on the order summary.",
        "priority": "Medium", "severity": "Minor", "status": "Done",
        "reporter": "tester1", "assignee": "dev1", "category": "Localization",
        "sprint": "closed", "fix_version": "released",
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Task",
        "title": "Write onboarding docs for new hires",
        "description": "Document the checkout module's architecture for the next engineer who touches it.",
        "priority": "Low", "reporter": "dev1", "category": "Documentation",
    }, users)
    count += 1

    return count


def seed_mobile_project(org_id: int, project: dict, users: dict) -> int:
    count = 0

    epic_id, _ = create_issue(org_id, project, {
        "type": "Epic", "title": "Offline Mode",
        "description": "Let the mobile app remain useful without a network connection.",
        "priority": "High", "severity": "Major", "status": "In Progress",
        "reporter": "pm", "assignee": "dev2", "category": "Mobile",
    }, users)
    count += 1

    story_id, _ = create_issue(org_id, project, {
        "type": "Story", "parent_id": epic_id,
        "title": "Cache recently viewed issues locally",
        "description": "As a user, I want to open an issue I recently viewed even with no signal.",
        "priority": "High", "severity": "Major", "status": "In Progress",
        "reporter": "pm", "assignee": "dev2", "category": "Mobile",
        "story_points": 5, "sprint": "active",
        "watchers": ["dev2"],
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Subtask", "parent_id": story_id,
        "title": "Implement local storage layer",
        "description": "SQLite-backed cache for issue detail views.",
        "priority": "High", "status": "In Progress",
        "reporter": "dev2", "assignee": "dev2", "category": "Mobile",
        "sprint": "active",
        "time_entries": [("dev2", 4.0, "Schema + read path")],
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Bug",
        "title": "App crashes on rotation (Android)",
        "description": "Rotating the device while viewing an issue detail screen force-closes the app.",
        "reproduction_steps": "1. Open any issue on Android\n2. Rotate device to landscape",
        "priority": "Critical", "severity": "Blocker", "status": "To Do",
        "reporter": "tester2", "assignee": "dev1", "category": "Mobile",
        "due_date": _d(3),
        "comments": [("tester2", "Happens on Pixel 7 and Pixel 8, not on iOS.")],
        "watchers": ["pm"],
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Bug",
        "title": "Push notifications arrive several minutes late",
        "description": "Status-change push notifications are frequently delayed by 5-10 minutes.",
        "priority": "Medium", "severity": "Major", "status": "Testing",
        "reporter": "tester1", "assignee": "dev2", "category": "Mobile",
        "sprint": "active",
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Task",
        "title": "Upgrade React Native to latest LTS",
        "description": "Currently two major versions behind.",
        "priority": "Low", "reporter": "dev2", "category": "Maintenance",
    }, users)
    count += 1

    _, _ = create_issue(org_id, project, {
        "type": "Story",
        "title": "Dark mode support",
        "description": "Respect the OS-level light/dark preference throughout the app.",
        "priority": "Medium", "severity": "Minor", "status": "Done",
        "reporter": "pm", "assignee": "dev1", "category": "Mobile",
        "story_points": 3, "sprint": "closed", "fix_version": "released",
        "time_entries": [("dev1", 8.0, "Theming pass across all screens")],
    }, users)
    count += 1

    return count


def main() -> int:
    existing = organization_repository.get_by_name(ORG_NAME)
    if existing is not None:
        print(f"'{ORG_NAME}' already exists (organization id={existing['id']}).")
        print("Refusing to seed a second copy. Delete that organization's data first")
        print("(cascading deletes will take its projects/issues/users with it), or")
        print("edit ORG_NAME at the top of this script to seed a differently-named org.")
        return 1

    try:
        print(f"Creating organization '{ORG_NAME}' and {len(USERS)} users...")
        org_id, users = create_org_and_users()

        print("Creating projects, sprints and versions...")
        web_project = create_project_with_sprints_and_versions(org_id, "Web Platform", "WEB")
        mob_project = create_project_with_sprints_and_versions(org_id, "Mobile App", "MOB")

        print("Creating issues (with hierarchy, comments, watchers, time entries)...")
        issue_count = seed_web_project(org_id, web_project, users)
        issue_count += seed_mobile_project(org_id, mob_project, users)

        print("Seeding the organization's default dashboard layout...")
        dashboard_service.ensure_org_defaults(org_id)

    except Exception as exc:
        print(f"  Seeding failed partway through: {exc}")
        print("  The database may now hold a partially-seeded organization --")
        print(f"  inspect or delete the '{ORG_NAME}' organization before retrying.")
        return 1

    print()
    print("Done. Log in with any of the following (all use the same password):")
    print(f"  password: {DUMMY_PASSWORD}")
    print()
    for full_name, email, role, _ in USERS:
        print(f"  {email:24s} {role:16s} {full_name}")
    print()
    print(f"Projects: {web_project['key']} (Web Platform), {mob_project['key']} (Mobile App)")
    print(f"Issues created: {issue_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
