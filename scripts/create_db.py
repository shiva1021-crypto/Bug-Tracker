"""Create the app's database if it does not already exist.

Run from the project root:
    python -m scripts.create_db

Idempotent: safe to run repeatedly. No tables are created here - the schema
starts arriving in a later stage. Exit code 0 on success, 1 on failure.
"""

import sys

import mysql.connector

from config import config


def main() -> int:
    db_name = config.DB_NAME
    print(f"Ensuring database '{db_name}' exists on "
          f"{config.DB_HOST}:{config.DB_PORT} ...")
    try:
        conn = mysql.connector.connect(
            connection_timeout=5,
            **config.db_connection_kwargs(include_database=False),
        )
    except mysql.connector.Error as exc:
        print(f"  Could not connect to MySQL: {exc}")
        return 1

    try:
        cursor = conn.cursor()
        # Identifier can't be parameterised; DB_NAME is operator-controlled config.
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
        cursor.close()
    except mysql.connector.Error as exc:
        print(f"  Failed to create database: {exc}")
        return 1
    finally:
        conn.close()

    print(f"  Database '{db_name}' is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
