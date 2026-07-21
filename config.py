"""Environment-based configuration for the Bug Tracker app.

Loads values from a `.env` file (via python-dotenv) and exposes a single
`Config` object. Nothing here is hardcoded per-environment: behaviour is driven
entirely by `APP_ENV` and the individual environment variables.

Secret key policy:
  - production: `SECRET_KEY` MUST be explicitly set to a strong value. If it is
    missing, too short, or a known weak/placeholder value, the app refuses to
    boot (a ValueError is raised).
  - development: if `SECRET_KEY` is not provided, one is auto-generated and
    persisted to `.secret_key` on disk, so it stays stable across restarts.
"""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# Load .env once, at import time, from the project root.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY_FILE = BASE_DIR / ".secret_key"

# Values we never accept as a "real" secret key in production.
_WEAK_SECRET_KEYS = {
    "",
    "dev",
    "development",
    "changeme",
    "change-me",
    "secret",
    "secret-key",
    "secretkey",
    "default",
    "please-change-me",
    "your-secret-key",
}
_MIN_SECRET_KEY_LENGTH = 32


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _resolve_secret_key(app_env: str) -> str:
    """Return a session secret key, enforcing the production policy."""
    provided = os.getenv("SECRET_KEY", "").strip()

    if app_env == "production":
        if provided.lower() in _WEAK_SECRET_KEYS or len(provided) < _MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                "Refusing to start in production: SECRET_KEY must be explicitly "
                f"set to a strong value (at least {_MIN_SECRET_KEY_LENGTH} "
                "characters and not a default/placeholder). Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return provided

    # Development: use the provided key if any, else persist a generated one.
    if provided:
        return provided

    if SECRET_KEY_FILE.exists():
        stored = SECRET_KEY_FILE.read_text(encoding="utf-8").strip()
        if stored:
            return stored

    generated = secrets.token_urlsafe(48)
    SECRET_KEY_FILE.write_text(generated, encoding="utf-8")
    return generated


class Config:
    """Single configuration object built from environment variables."""

    APP_ENV: str = os.getenv("APP_ENV", "development").strip().lower()
    IS_PRODUCTION: bool = APP_ENV == "production"

    SECRET_KEY: str = _resolve_secret_key(APP_ENV)

    # Database
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = _int_env("DB_PORT", 3306)
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "bug_tracker_db")
    DB_POOL_SIZE: int = _int_env("DB_POOL_SIZE", 5)

    # Session cookie
    SESSION_COOKIE_SECURE: bool = _bool_env("SESSION_COOKIE_SECURE", False)
    SESSION_LIFETIME_SECONDS: int = _int_env("SESSION_LIFETIME_SECONDS", 28800)

    # Stage 5: where issue screenshots are stored. Deliberately NOT under
    # static/ -- the spec requires uploads live somewhere that isn't
    # web-servable directly, so they're only ever reachable through the
    # authenticated, organization-scoped `/issues/<id>/screenshot` route.
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    SCREENSHOT_UPLOAD_DIR: Path = BASE_DIR / "uploads" / "screenshots"

    # Stage 10: absolute base URL used to build links inside notification
    # emails (e.g. "http://localhost:5000/issues/42"). A request's own Host
    # header isn't available from the background worker thread, which has
    # no request context at all, so this must be configured explicitly
    # rather than derived from `request`.
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")

    # Stage 10: email notifications. SMTP_HOST left blank means "not
    # configured" -- the background worker (services/notification_worker.py)
    # treats that as "nothing to do this cycle" rather than an error, so
    # the app runs fine with no mail server at all; rows just queue up in
    # `email_outbox` until SMTP is configured.
    SMTP_HOST: str = os.getenv("SMTP_HOST", "").strip()
    SMTP_PORT: int = _int_env("SMTP_PORT", 587)
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "").strip()
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = _bool_env("SMTP_USE_TLS", True)
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "bugtracker@example.com").strip()

    # Per the spec: "Make it configurable to disable entirely... for
    # environments without SMTP configured, so the app still runs without
    # crashing." Defaults on; set to false to skip starting the background
    # thread altogether (outbox rows still get written, just never sent).
    NOTIFICATION_WORKER_ENABLED: bool = _bool_env("NOTIFICATION_WORKER_ENABLED", True)
    NOTIFICATION_WORKER_INTERVAL_SECONDS: int = _int_env("NOTIFICATION_WORKER_INTERVAL_SECONDS", 10)

    # Stage 10: rate limiting. "memory" (default) needs nothing extra and
    # works for a single process; "database" persists counters in
    # `auth_rate_limits` so the limit is shared across multiple app
    # instances behind a load balancer.
    RATELIMIT_STORAGE: str = os.getenv("RATELIMIT_STORAGE", "memory").strip().lower()
    RATELIMIT_MAX_ATTEMPTS: int = _int_env("RATELIMIT_MAX_ATTEMPTS", 5)
    RATELIMIT_WINDOW_SECONDS: int = _int_env("RATELIMIT_WINDOW_SECONDS", 900)

    @classmethod
    def db_connection_kwargs(cls, include_database: bool = True) -> dict:
        """Keyword args for a MySQL connection.

        `include_database=False` is used by setup scripts that need to connect
        to the server before the app's database exists.
        """
        kwargs = {
            "host": cls.DB_HOST,
            "port": cls.DB_PORT,
            "user": cls.DB_USER,
            "password": cls.DB_PASSWORD,
        }
        if include_database:
            kwargs["database"] = cls.DB_NAME
        return kwargs


# Instantiated eagerly so import-time errors (e.g. weak prod key) fail fast.
config = Config()
