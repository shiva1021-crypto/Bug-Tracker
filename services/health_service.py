"""Business rules for status/health reporting.

Services translate raw repository/plumbing results into the shapes the route
layer returns. Routes never talk to the database directly; they go through here.
"""

from config import config
from repositories import health_repository

APP_NAME = "Bug Tracker"
STAGE = 1


def app_status() -> dict:
    """Basic app status for the `/` route (no database involved)."""
    return {
        "name": APP_NAME,
        "stage": STAGE,
        "status": "ok",
        "environment": config.APP_ENV,
    }


def db_status() -> tuple[dict, int]:
    """Check database reachability for `/health/db`.

    Returns a (payload, http_status) tuple: 200 when the pooled connection
    succeeds, 503 with a clean error message when it does not. No stack trace
    escapes to the client.
    """
    try:
        health_repository.ping()
    except Exception as exc:  # noqa: BLE001 - report any DB failure cleanly
        return (
            {
                "status": "unavailable",
                "database": config.DB_NAME,
                "error": str(exc),
            },
            503,
        )
    return (
        {
            "status": "ok",
            "database": config.DB_NAME,
        },
        200,
    )
