"""Create the tables this stage requires, if they do not already exist.

Run from the project root:
    python -m scripts.create_tables

Idempotent: every CREATE TABLE uses IF NOT EXISTS, and the users-table
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

# Order matters: organizations before users/projects/registration_requests
# (all three FK to it). users is created here only for a brand-new
# database; on an existing Stage-2 database this is a no-op and
# _migrate_users_table() below handles adding the new columns.
STATEMENTS = [
    ("organizations", ORGANIZATIONS_TABLE),
    ("users", USERS_TABLE),
    ("registration_requests", REGISTRATION_REQUESTS_TABLE),
    ("projects", PROJECTS_TABLE),
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
