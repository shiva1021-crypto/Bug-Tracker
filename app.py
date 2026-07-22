"""Flask application factory.

Wires configuration, session settings, and route blueprints together. Importing
`config` at module load enforces the secret-key policy (in production a
weak/missing SECRET_KEY makes this raise before the app can serve traffic).
"""

import os
from datetime import timedelta

import mysql.connector
from flask import Flask, render_template, request

from config import config
from repositories import organization_repository
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
from routes.automation_routes import automation_bp
from routes.backlog_routes import backlog_bp
from routes.board_routes import board_bp
from routes.dashboard_routes import dashboard_bp
from routes.field_routes import field_bp
from routes.filter_routes import filter_bp
from routes.health_routes import health_bp
from routes.issue_routes import issue_bp
from routes.project_routes import project_bp
from routes.report_routes import report_bp
from routes.version_routes import version_bp
from services import notification_worker
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
    app.register_blueprint(board_bp)
    app.register_blueprint(backlog_bp)
    app.register_blueprint(filter_bp)
    app.register_blueprint(field_bp)
    app.register_blueprint(automation_bp)
    app.register_blueprint(version_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(report_bp)

    # Stage 10: start the email-outbox background worker, once.
    #
    # Under the Flask dev server's reloader (`python run.py`, debug=True),
    # this module is imported twice: once by the watcher parent process
    # (which never serves traffic) and once by the actual child process
    # that does (marked by WERKZEUG_RUN_MAIN=true). Starting the thread in
    # the parent too would leave an orphaned worker running against a
    # process that never accepts a request. In production there is no
    # reloader at all, so the guard just falls through to "always start."
    if config.IS_PRODUCTION or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        notification_worker.start()

    @app.errorhandler(404)
    def not_found(_error):
        """One generic 404 page. Deliberately uninformative: an issue id
        that doesn't exist and one that belongs to another organization
        both land here via the same `abort(404)`, so the response can't be
        used to distinguish the two cases."""
        return render_template("errors/404.html"), 404

    @app.errorhandler(mysql.connector.Error)
    def database_unreachable(error):
        """Stage 10's cloned `database_error.html` (per the spec's Frontend
        section) isn't reachable from anywhere in the route table on its
        own -- there's no dedicated route for it, just a template to clone.
        The only way it's ever actually shown to a developer is if
        something in the request raises a `mysql.connector.Error`, so this
        handler is the minimal plumbing needed to make that cloned page do
        anything at all, the same reasoning already used for
        infrastructure the route table doesn't spell out (Stage 5's
        screenshot route, Stage 8/9's delete routes). Every DB call in this
        app goes through `utils/db.py::get_connection()`, which raises this
        exact exception class on a connection failure, so catching it here
        covers "MySQL isn't running," "wrong port," "wrong password," and
        "database/tables don't exist yet" uniformly -- exactly the set of
        problems reference's own fix checklist walks through.
        """
        return render_template("errors/database_error.html", error=error), 500

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

    @app.template_filter("label_color_index")
    def label_color_index(label: str) -> int:
        """Deterministic small-palette index for a label's colored dot on
        the Stage 7 board. There is no per-label color column (labels are
        just a comma-separated VARCHAR, unchanged since Stage 5), so the
        same label text always maps to the same one of a handful of CSS
        dot colors (`static/style.css`'s `.board-label-dot-0`..`-5`)
        instead of a random/positional color.
        """
        return sum(ord(char) for char in label) % 6

    @app.context_processor
    def inject_globals():
        """Make `current_user`, `csrf_token()`, and the caller's organization
        name available in every template. `current_organization_name` backs
        the reference-ui sidebar's org badge (base.html) -- the session only
        caches `organization_id` (see utils/auth.py), so the name is looked
        up here, once per request, rather than duplicating it into the
        session cache.
        """
        user = current_user()
        organization_name = None
        if user is not None:
            try:
                organization = organization_repository.get_by_id(user["organization_id"])
                organization_name = organization["name"] if organization else None
            except mysql.connector.Error:
                # base.html (and therefore errors/database_error.html,
                # which extends it) renders for every response, including
                # the database-unreachable error page itself. Without this
                # guard, a DB outage would make *this* lookup fail too,
                # turning the friendly error page into an unhandled
                # exception instead of the message it's supposed to show.
                organization_name = None
        return {
            "current_user": user,
            "csrf_token": generate_csrf_token,
            "current_organization_name": organization_name,
        }

    return app


# Module-level app instance for `flask run` and WSGI servers.
app = create_app()
