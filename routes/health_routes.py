"""HTTP handlers for app + database health.

The route layer is thin: parse/return HTTP, delegate all logic to services.
"""

from flask import Blueprint, jsonify

from services import health_service

health_bp = Blueprint("health", __name__)


@health_bp.get("/")
def index():
    """Basic app status. No auth."""
    return jsonify(health_service.app_status()), 200


@health_bp.get("/health/db")
def health_db():
    """Verify the database is reachable via a pooled connection. No auth.

    200 when MySQL is up, clean 503 (no stack trace) when it is not.
    """
    payload, status = health_service.db_status()
    return jsonify(payload), status
