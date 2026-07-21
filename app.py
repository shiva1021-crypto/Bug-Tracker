"""Flask application factory.

Wires configuration, session settings, and route blueprints together. Importing
`config` at module load enforces the secret-key policy (in production a
weak/missing SECRET_KEY makes this raise before the app can serve traffic).
"""

from datetime import timedelta

from flask import Flask, render_template, request

from config import config
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
from routes.health_routes import health_bp
from routes.issue_routes import issue_bp
from routes.project_routes import project_bp
from utils.auth import current_user
from utils.security import CSRF_FORM_FIELD, generate_csrf_token, validate_csrf_token


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
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(project_bp)
    app.register_blueprint(issue_bp)

    @app.errorhandler(404)
    def not_found(_error):
        """One generic 404 page. Deliberately uninformative: an issue id
        that doesn't exist and one that belongs to another organization
        both land here via the same `abort(404)`, so the response can't be
        used to distinguish the two cases."""
        return render_template("errors/404.html"), 404

    @app.before_request
    def enforce_csrf():
        """Validate the CSRF token on every state-changing request.

        Applied centrally so a new POST route cannot forget it.
        """
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if not validate_csrf_token(request.form.get(CSRF_FORM_FIELD)):
                return render_template("errors/400.html"), 400
        return None

    @app.after_request
    def no_store(response):
        """Stop the browser caching authenticated pages.

        Without this, pressing Back after logout can redisplay a protected page
        straight from the browser's cache.
        """
        if request.endpoint != "static":
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.context_processor
    def inject_globals():
        """Make `current_user` and `csrf_token()` available in every template."""
        return {
            "current_user": current_user(),
            "csrf_token": generate_csrf_token,
        }

    return app


# Module-level app instance for `flask run` and WSGI servers.
app = create_app()
