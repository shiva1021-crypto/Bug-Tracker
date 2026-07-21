"""Flask application factory.

Wires configuration, session settings, and route blueprints together. Importing
`config` at module load enforces the secret-key policy (in production a
weak/missing SECRET_KEY makes this raise before the app can serve traffic).
"""

from datetime import timedelta

from flask import Flask

from config import config
from routes.health_routes import health_bp


def create_app() -> Flask:
    app = Flask(__name__)

    # Session / security configuration.
    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=config.SESSION_LIFETIME_SECONDS),
    )

    # Blueprints (route layer).
    app.register_blueprint(health_bp)

    return app


# Module-level app instance for `flask run` and WSGI servers.
app = create_app()
