"""Create the tables this stage requires, if they do not already exist.

Run from the project root:
    python -m scripts.create_tables

Idempotent: every CREATE TABLE uses IF NOT EXISTS and the users-table
migration (adding organization_id / role) checks information_schema before
altering anything, so re-running this script is always safe.

Assumes the database itself already exists (see `scripts.create_db`).
Exit code 0 on success, 1 on failure.
"""

import sys

import mysql.connector

from config import config

USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    full_name     VARCHAR(150)  NOT NULL,
    email         VARCHAR(150)  NOT NULL UNIQUE,
    password_hash VARCHAR(255)  NOT NULL,
    created_at    DATETIME      DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

ORGANIZATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS organizations (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(150) NOT NULL UNIQUE,
    created_at DATETIME     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

REGISTRATION_REQUESTS_TABLE = """
CREATE TABLE IF NOT EXISTS registration_requests (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    organization_id  INT NOT NULL,
    full_name        VARCHAR(150) NOT NULL,
    email            VARCHAR(150) NOT NULL,
    password_hash    VARCHAR(255) NOT NULL,
    requested_role   ENUM('admin','project_manager','developer','tester')
                     NOT NULL DEFAULT 'tester',
    requester_ip     VARCHAR(45),
    status           ENUM('pending','approved','rejected')
                     NOT NULL DEFAULT 'pending',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_registration_requests_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

PROJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    organization_id    INT NOT NULL,
    name               VARCHAR(150) NOT NULL,
    project_key        VARCHAR(10) NOT NULL,
    description        TEXT,
    next_issue_number  INT NOT NULL DEFAULT 1,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_projects_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id)
        ON DELETE CASCADE,
    CONSTRAINT uq_projects_org_key UNIQUE (organization_id, project_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

SPRINTS_TABLE = """
CREATE TABLE IF NOT EXISTS sprints (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    organization_id  INT NOT NULL,
    project_id       INT NOT NULL,
    name             VARCHAR(120) NOT NULL,
    goal             TEXT,
    start_date       DATE,
    end_date         DATE,
    status           ENUM('future','active','closed') NOT NULL DEFAULT 'future',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sprints_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_sprints_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

VERSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS versions (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    organization_id  INT NOT NULL,
    project_id       INT NOT NULL,
    name             VARCHAR(120) NOT NULL,
    description      TEXT,
    release_date     DATE,
    status           ENUM('unreleased','released','archived') NOT NULL DEFAULT 'unreleased',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_versions_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_versions_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT uq_versions_project_name UNIQUE (project_id, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

BUGS_TABLE = """
CREATE TABLE IF NOT EXISTS bugs (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    organization_id     INT NOT NULL,
    project_id          INT NOT NULL,
    issue_key           VARCHAR(30) NOT NULL,
    issue_type          ENUM('Epic','Story','Task','Bug','Subtask') NOT NULL,
    parent_id           INT NULL,
    title               VARCHAR(255) NOT NULL,
    description         TEXT NOT NULL,
    reproduction_steps  TEXT,
    category            VARCHAR(80) NOT NULL DEFAULT 'General',
    priority            ENUM('Low','Medium','High','Critical') NOT NULL DEFAULT 'Medium',
    severity            ENUM('Minor','Major','Critical','Blocker') NOT NULL DEFAULT 'Minor',
    status              VARCHAR(50) NOT NULL DEFAULT 'Idea',
    reporter_id         INT NOT NULL,
    assigned_to         INT NULL,
    screenshot_path     VARCHAR(255),
    labels              VARCHAR(255),
    story_points        INT,
    due_date            DATE,
    sprint_id           INT NULL,
    time_estimate       DECIMAL(10,2) NULL,
    time_remaining      DECIMAL(10,2) NULL,
    fix_version_id      INT NULL,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_bugs_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_bugs_project
        FOREIGN KEY (project_id) REFERENCES projects(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_bugs_parent
        FOREIGN KEY (parent_id) REFERENCES bugs(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_bugs_reporter
        FOREIGN KEY (reporter_id) REFERENCES users(id),
    CONSTRAINT fk_bugs_assigned_to
        FOREIGN KEY (assigned_to) REFERENCES users(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_bugs_sprint
        FOREIGN KEY (sprint_id) REFERENCES sprints(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_bugs_fix_version
        FOREIGN KEY (fix_version_id) REFERENCES versions(id)
        ON DELETE SET NULL,
    CONSTRAINT uq_bugs_org_key UNIQUE (organization_id, issue_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

COMMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS comments (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    bug_id     INT NOT NULL,
    user_id    INT NOT NULL,
    comment    TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comments_bug FOREIGN KEY (bug_id) REFERENCES bugs(id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

BUG_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS bug_history (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    bug_id           INT NOT NULL,
    changed_by       INT NOT NULL,
    old_status       VARCHAR(50),
    new_status       VARCHAR(50),
    old_assigned_to  INT,
    new_assigned_to  INT,
    change_note      VARCHAR(255),
    changed_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_bug_history_bug FOREIGN KEY (bug_id) REFERENCES bugs(id) ON DELETE CASCADE,
    CONSTRAINT fk_bug_history_changed_by FOREIGN KEY (changed_by) REFERENCES users(id),
    CONSTRAINT fk_bug_history_old_assigned FOREIGN KEY (old_assigned_to) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_bug_history_new_assigned FOREIGN KEY (new_assigned_to) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

ISSUE_WATCHERS_TABLE = """
CREATE TABLE IF NOT EXISTS issue_watchers (
    bug_id  INT NOT NULL,
    user_id INT NOT NULL,
    PRIMARY KEY (bug_id, user_id),
    CONSTRAINT fk_issue_watchers_bug FOREIGN KEY (bug_id) REFERENCES bugs(id) ON DELETE CASCADE,
    CONSTRAINT fk_issue_watchers_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

ISSUE_LINKS_TABLE = """
CREATE TABLE IF NOT EXISTS issue_links (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    bug_id_a   INT NOT NULL,
    bug_id_b   INT NOT NULL,
    link_type  ENUM('blocks','relates_to','duplicates','clones') NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_issue_links_bug_a FOREIGN KEY (bug_id_a) REFERENCES bugs(id) ON DELETE CASCADE,
    CONSTRAINT fk_issue_links_bug_b FOREIGN KEY (bug_id_b) REFERENCES bugs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

SAVED_FILTERS_TABLE = """
CREATE TABLE IF NOT EXISTS saved_filters (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    organization_id INT NOT NULL,
    name            VARCHAR(120) NOT NULL,
    filter_data     JSON NOT NULL,
    is_shared       TINYINT(1) NOT NULL DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_saved_filters_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_saved_filters_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

CUSTOM_FIELD_DEFINITIONS_TABLE = """
CREATE TABLE IF NOT EXISTS custom_field_definitions (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    organization_id  INT NOT NULL,
    project_id       INT NOT NULL,
    name             VARCHAR(120) NOT NULL,
    field_type       ENUM('text','number','date','dropdown','checkbox') NOT NULL,
    options          JSON,
    required         TINYINT(1) NOT NULL DEFAULT 0,
    display_order    INT NOT NULL DEFAULT 0,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_custom_field_definitions_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_custom_field_definitions_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

CUSTOM_FIELD_VALUES_TABLE = """
CREATE TABLE IF NOT EXISTS custom_field_values (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    bug_id    INT NOT NULL,
    field_id  INT NOT NULL,
    value     TEXT,
    CONSTRAINT fk_custom_field_values_bug FOREIGN KEY (bug_id) REFERENCES bugs(id) ON DELETE CASCADE,
    CONSTRAINT fk_custom_field_values_field FOREIGN KEY (field_id) REFERENCES custom_field_definitions(id) ON DELETE CASCADE,
    CONSTRAINT uq_custom_field_values_bug_field UNIQUE (bug_id, field_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

AUTOMATION_RULES_TABLE = """
CREATE TABLE IF NOT EXISTS automation_rules (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    organization_id  INT NOT NULL,
    project_id       INT NULL,
    name             VARCHAR(150) NOT NULL,
    trigger_event    ENUM('issue_created','status_changed','field_updated') NOT NULL,
    conditions       JSON,
    actions          JSON NOT NULL,
    enabled          TINYINT(1) NOT NULL DEFAULT 1,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_automation_rules_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_automation_rules_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

TIME_ENTRIES_TABLE = """
CREATE TABLE IF NOT EXISTS time_entries (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    bug_id       INT NOT NULL,
    user_id      INT NOT NULL,
    hours_spent  DECIMAL(10,2) NOT NULL,
    description  TEXT,
    logged_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_time_entries_bug FOREIGN KEY (bug_id) REFERENCES bugs(id) ON DELETE CASCADE,
    CONSTRAINT fk_time_entries_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

DASHBOARD_WIDGETS_TABLE = """
CREATE TABLE IF NOT EXISTS dashboard_widgets (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    organization_id  INT NOT NULL,
    user_id          INT NULL,
    widget_type      ENUM('stats_summary','recent_issues','issues_by_status',
                          'issues_by_priority','issues_by_severity','issues_by_type')
                     NOT NULL,
    title            VARCHAR(120) NOT NULL,
    config           JSON,
    position         INT NOT NULL DEFAULT 0,
    width            ENUM('full','half','third') NOT NULL DEFAULT 'half',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_dashboard_widgets_organization FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT fk_dashboard_widgets_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

EMAIL_OUTBOX_TABLE = """
CREATE TABLE IF NOT EXISTS email_outbox (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    to_email   VARCHAR(150) NOT NULL,
    subject    VARCHAR(255) NOT NULL,
    body       TEXT NOT NULL,
    status     ENUM('pending','sent','failed') NOT NULL DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    sent_at    DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

AUTH_RATE_LIMITS_TABLE = """
CREATE TABLE IF NOT EXISTS auth_rate_limits (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    identifier         VARCHAR(150) NOT NULL,
    attempt_count      INT NOT NULL DEFAULT 0,
    window_started_at  DATETIME NOT NULL,
    CONSTRAINT uq_auth_rate_limits_identifier UNIQUE (identifier)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# Order matters: organizations before users/projects/registration_requests;
# projects before sprints/versions (both FK to it) and before bugs; sprints
# and versions before bugs (bugs.sprint_id and bugs.fix_version_id FK to
# them respectively); bugs before comments/bug_history/issue_watchers/
# issue_links/custom_field_values/time_entries (all FK to it);
# custom_field_definitions before custom_field_values (FKs to it) and
# before bugs is NOT required (custom_field_values, not bugs, is what FKs
# to custom_field_definitions) but is created here regardless since it
# also needs projects/organizations first. saved_filters and
# automation_rules only need users/projects/organizations, so either can
# go anywhere after those. users is created here only for a brand-new
# database; on an existing Stage-2 database this is a no-op and
# _migrate_users_table() below handles adding the new columns.
STATEMENTS = [
    ("organizations", ORGANIZATIONS_TABLE),
    ("users", USERS_TABLE),
    ("registration_requests", REGISTRATION_REQUESTS_TABLE),
    ("projects", PROJECTS_TABLE),
    ("sprints", SPRINTS_TABLE),
    ("versions", VERSIONS_TABLE),
    ("custom_field_definitions", CUSTOM_FIELD_DEFINITIONS_TABLE),
    ("bugs", BUGS_TABLE),
    ("comments", COMMENTS_TABLE),
    ("bug_history", BUG_HISTORY_TABLE),
    ("issue_watchers", ISSUE_WATCHERS_TABLE),
    ("issue_links", ISSUE_LINKS_TABLE),
    ("saved_filters", SAVED_FILTERS_TABLE),
    ("custom_field_values", CUSTOM_FIELD_VALUES_TABLE),
    ("automation_rules", AUTOMATION_RULES_TABLE),
    ("time_entries", TIME_ENTRIES_TABLE),
    # Stage 10: dashboard_widgets needs organizations/users to exist first;
    # email_outbox and auth_rate_limits have no foreign keys at all (an
    # outbox row and a rate-limit counter are both identified by a plain
    # string -- an email address or an IP -- never a tenant id), so their
    # position in this list is arbitrary.
    ("dashboard_widgets", DASHBOARD_WIDGETS_TABLE),
    ("email_outbox", EMAIL_OUTBOX_TABLE),
    ("auth_rate_limits", AUTH_RATE_LIMITS_TABLE),
]


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (config.DB_NAME, table, column),
    )
    return cursor.fetchone()[0] > 0


def _constraint_exists(cursor, table: str, constraint_name: str) -> bool:
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = %s AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s",
        (config.DB_NAME, table, constraint_name),
    )
    return cursor.fetchone()[0] > 0


def _migrate_users_table(cursor) -> None:
    """Add organization_id + role to an existing `users` table, safely.

    Stage 2 created `users` with neither column. If rows already exist (real
    accounts created while testing Stage 2), adding organization_id as
    NOT NULL directly would fail outright -- there is no organization for an
    existing row to point at yet. So: add it nullable, backfill any existing
    rows into a single "Legacy Organization" (as admin, so nobody loses
    access), tighten to NOT NULL, then add the FK. On a fresh database with
    no rows this whole backfill step is a no-op beyond the ALTER itself.
    """
    added_org_column = False

    if not _column_exists(cursor, "users", "organization_id"):
        cursor.execute("ALTER TABLE users ADD COLUMN organization_id INT NULL")
        added_org_column = True
        print("  Added users.organization_id (nullable, backfilling next).")

    if not _column_exists(cursor, "users", "role"):
        cursor.execute(
            "ALTER TABLE users ADD COLUMN role "
            "ENUM('admin','project_manager','developer','tester') "
            "NOT NULL DEFAULT 'tester'"
        )
        print("  Added users.role (default 'tester').")

    if added_org_column:
        cursor.execute("SELECT id FROM users WHERE organization_id IS NULL")
        orphans = cursor.fetchall()
        if orphans:
            cursor.execute(
                "INSERT INTO organizations (name) VALUES (%s)",
                ("Legacy Organization",),
            )
            legacy_org_id = cursor.lastrowid
            cursor.execute(
                "UPDATE users SET organization_id = %s, role = 'admin' "
                "WHERE organization_id IS NULL",
                (legacy_org_id,),
            )
            print(
                f"  Backfilled {len(orphans)} pre-existing user(s) into "
                f"'Legacy Organization' (id={legacy_org_id}) as admin."
            )
        cursor.execute("ALTER TABLE users MODIFY COLUMN organization_id INT NOT NULL")
        print("  users.organization_id is now NOT NULL.")

    if not _constraint_exists(cursor, "users", "fk_users_organization"):
        cursor.execute(
            "ALTER TABLE users ADD CONSTRAINT fk_users_organization "
            "FOREIGN KEY (organization_id) REFERENCES organizations(id) "
            "ON DELETE CASCADE"
        )
        print("  Added FK users.organization_id -> organizations.id.")


def _ensure_bugs_status_default(cursor) -> None:
    """Change bugs.status's column default from Stage 5's 'To Do' to 'Idea'.

    Stage 5 left the exact default ambiguous ("'Idea' or 'To Do'") and chose
    'To Do'. Stage 6 defines the canonical five-status order starting at
    'Idea', which supersedes that choice -- see STAGE-06-REPORT.md. Safe to
    re-run: setting a column default to the same value twice is a no-op.
    New issues get their status from `issue_service.DEFAULT_STATUS` at
    insert time regardless, so this ALTER is really just keeping the
    schema's own documentation (and any manual/direct SQL insert) honest.
    """
    cursor.execute("ALTER TABLE bugs ALTER COLUMN status SET DEFAULT 'Idea'")
    print("  bugs.status default is now 'Idea' (was 'To Do' in Stage 5).")


def _ensure_bugs_sprint_column(cursor) -> None:
    """Add `bugs.sprint_id` (+ its FK to `sprints`) to a database that ran
    an earlier stage's version of this script before Stage 8 existed.

    A brand-new database gets this column directly from `BUGS_TABLE`'s own
    DDL above (which already lists `sprint_id` and its FK) -- this function
    only matters for a database that already has a `bugs` table without it.
    Checks `information_schema` first, exactly like `_migrate_users_table`,
    so re-running this script is always safe.
    """
    if not _column_exists(cursor, "bugs", "sprint_id"):
        cursor.execute("ALTER TABLE bugs ADD COLUMN sprint_id INT NULL")
        print("  Added bugs.sprint_id (nullable).")

    if not _constraint_exists(cursor, "bugs", "fk_bugs_sprint"):
        cursor.execute(
            "ALTER TABLE bugs ADD CONSTRAINT fk_bugs_sprint "
            "FOREIGN KEY (sprint_id) REFERENCES sprints(id) ON DELETE SET NULL"
        )
        print("  Added FK bugs.sprint_id -> sprints.id.")


def _ensure_bugs_stage9_columns(cursor) -> None:
    """Add `bugs.time_estimate`, `bugs.time_remaining` and
    `bugs.fix_version_id` (+ its FK to `versions`) to a database that ran
    an earlier stage's version of this script before Stage 9 existed.

    A brand-new database gets all three directly from `BUGS_TABLE`'s own
    DDL above -- this function only matters for a database whose `bugs`
    table predates Stage 9. Checks `information_schema` first, exactly
    like `_migrate_users_table` and `_ensure_bugs_sprint_column`, so
    re-running this script is always safe.
    """
    if not _column_exists(cursor, "bugs", "time_estimate"):
        cursor.execute("ALTER TABLE bugs ADD COLUMN time_estimate DECIMAL(10,2) NULL")
        print("  Added bugs.time_estimate (nullable).")

    if not _column_exists(cursor, "bugs", "time_remaining"):
        cursor.execute("ALTER TABLE bugs ADD COLUMN time_remaining DECIMAL(10,2) NULL")
        print("  Added bugs.time_remaining (nullable).")

    if not _column_exists(cursor, "bugs", "fix_version_id"):
        cursor.execute("ALTER TABLE bugs ADD COLUMN fix_version_id INT NULL")
        print("  Added bugs.fix_version_id (nullable).")

    if not _constraint_exists(cursor, "bugs", "fk_bugs_fix_version"):
        cursor.execute(
            "ALTER TABLE bugs ADD CONSTRAINT fk_bugs_fix_version "
            "FOREIGN KEY (fix_version_id) REFERENCES versions(id) ON DELETE SET NULL"
        )
        print("  Added FK bugs.fix_version_id -> versions.id.")


def main() -> int:
    print(f"Creating tables in '{config.DB_NAME}' on "
          f"{config.DB_HOST}:{config.DB_PORT} ...")
    try:
        conn = mysql.connector.connect(
            connection_timeout=5,
            **config.db_connection_kwargs(include_database=True),
        )
    except mysql.connector.Error as exc:
        print(f"  Could not connect to the database: {exc}")
        print(f"  Does '{config.DB_NAME}' exist? Run: python -m scripts.create_db")
        return 1

    try:
        cursor = conn.cursor()
        for name, ddl in STATEMENTS:
            cursor.execute(ddl)
            print(f"  Table '{name}' is ready.")
        _migrate_users_table(cursor)
        _ensure_bugs_status_default(cursor)
        _ensure_bugs_sprint_column(cursor)
        _ensure_bugs_stage9_columns(cursor)
        conn.commit()
        cursor.close()
    except mysql.connector.Error as exc:
        conn.rollback()
        print(f"  Failed to create/migrate tables: {exc}")
        return 1
    finally:
        conn.close()

    print("  Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
