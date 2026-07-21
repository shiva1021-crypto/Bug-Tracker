"""Verify MySQL is reachable and report whether the app's database exists.

Run from the project root:
    python -m scripts.check_db

Connects to the MySQL *server* (not a specific database), so it works even
before the app's database has been created. Exit code 0 on success, 1 on
failure.
"""

import sys

import mysql.connector

from config import config


def main() -> int:
    print(f"Connecting to MySQL at {config.DB_HOST}:{config.DB_PORT} "
          f"as '{config.DB_USER}' ...")
    try:
        conn = mysql.connector.connect(
            connection_timeout=5,
            **config.db_connection_kwargs(include_database=False),
        )
    except mysql.connector.Error as exc:
        print(f"  MySQL is NOT reachable: {exc}")
        return 1

    try:
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES LIKE %s", (config.DB_NAME,))
        exists = cursor.fetchone() is not None
        cursor.close()
    finally:
        conn.close()

    print("  MySQL is reachable.")
    if exists:
        print(f"  Database '{config.DB_NAME}' exists.")
    else:
        print(f"  Database '{config.DB_NAME}' does NOT exist yet. "
              f"Create it with: python -m scripts.create_db")
    return 0


if __name__ == "__main__":
    sys.exit(main())
