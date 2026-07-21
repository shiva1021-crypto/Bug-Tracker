"""Create the tables this stage requires, if they do not already exist.

Run from the project root:
    python -m scripts.create_tables

Idempotent: every statement uses IF NOT EXISTS, so re-running is safe.
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

STATEMENTS = [("users", USERS_TABLE)]


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
        conn.commit()
        cursor.close()
    except mysql.connector.Error as exc:
        print(f"  Failed to create tables: {exc}")
        return 1
    finally:
        conn.close()

    print("  Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
