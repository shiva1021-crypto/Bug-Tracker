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
