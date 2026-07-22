"""Rate limiting for login and registration attempts, per IP and per
account (email) -- slows down brute-force attempts without needing a
third-party dependency.

Two interchangeable backends, selected by `config.RATELIMIT_STORAGE`:

- "memory" (default): a module-level dict guarded by a lock. Simplest,
  works out of the box, but only limits attempts against *this* process --
  fine for a single app instance.
- "database": persists counters in `auth_rate_limits`, so the limit is
  shared across every app instance behind a load balancer.

Both implement the same three operations (`_is_blocked`, `_record_failure`,
`_record_success`), so `routes/auth_routes.py` never needs to know which
backend is active.

Design: only *failed* attempts count against the limit and a successful
attempt clears the counter immediately. This is the standard "account
lockout" shape (as opposed to counting every request, which would
eventually lock out a legitimate user who just logs in a lot) and is what
lets the Definition of Done's "resets after the configured window" be true
in the normal case too -- a real user's next correct login resets it
instantly rather than waiting out the window.
"""

import threading
import time

from config import config
from repositories import rate_limit_repository

_memory_lock = threading.Lock()
_memory_store: dict[str, dict] = {}  # identifier -> {"count": int, "window_started_at": float}


def _now() -> float:
    return time.time()


# ------------------------------------------------------------- memory backend --


def _memory_is_blocked(identifier: str) -> bool:
    with _memory_lock:
        entry = _memory_store.get(identifier)
        if entry is None:
            return False
        if _now() - entry["window_started_at"] > config.RATELIMIT_WINDOW_SECONDS:
            # Window has expired -- forget this identifier's history rather
            # than leaving a stale entry sitting around.
            del _memory_store[identifier]
            return False
        return entry["count"] >= config.RATELIMIT_MAX_ATTEMPTS


def _memory_record_failure(identifier: str) -> None:
    with _memory_lock:
        entry = _memory_store.get(identifier)
        now = _now()
        if entry is None or now - entry["window_started_at"] > config.RATELIMIT_WINDOW_SECONDS:
            _memory_store[identifier] = {"count": 1, "window_started_at": now}
        else:
            entry["count"] += 1


def _memory_record_success(identifier: str) -> None:
    with _memory_lock:
        _memory_store.pop(identifier, None)


# ----------------------------------------------------------- database backend --


def _database_is_blocked(identifier: str) -> bool:
    row = rate_limit_repository.get(identifier)
    if row is None:
        return False
    age_seconds = (_now() - row["window_started_at"].timestamp())
    if age_seconds > config.RATELIMIT_WINDOW_SECONDS:
        return False
    return row["attempt_count"] >= config.RATELIMIT_MAX_ATTEMPTS


def _database_record_failure(identifier: str) -> None:
    import datetime

    row = rate_limit_repository.get(identifier)
    now = datetime.datetime.now()
    if row is None:
        rate_limit_repository.upsert_increment(identifier, now)
        return
    age_seconds = (_now() - row["window_started_at"].timestamp())
    if age_seconds > config.RATELIMIT_WINDOW_SECONDS:
        rate_limit_repository.reset_window(identifier, now)
    else:
        rate_limit_repository.upsert_increment(identifier, row["window_started_at"])


def _database_record_success(identifier: str) -> None:
    rate_limit_repository.clear(identifier)


# ------------------------------------------------------------------- public --


def is_blocked(identifier: str) -> bool:
    """True if `identifier` (an IP or a normalized email) has hit the
    attempt cap within the current window."""
    if not identifier:
        return False
    if config.RATELIMIT_STORAGE == "database":
        return _database_is_blocked(identifier)
    return _memory_is_blocked(identifier)


def record_failure(identifier: str) -> None:
    if not identifier:
        return
    if config.RATELIMIT_STORAGE == "database":
        _database_record_failure(identifier)
    else:
        _memory_record_failure(identifier)


def record_success(identifier: str) -> None:
    if not identifier:
        return
    if config.RATELIMIT_STORAGE == "database":
        _database_record_success(identifier)
    else:
        _memory_record_success(identifier)


def seconds_until_reset(identifier: str) -> int:
    """Best-effort "try again in N seconds" figure for the error message.
    Returns the full window length if the identifier isn't tracked (should
    not normally be called in that case, but never raises)."""
    if config.RATELIMIT_STORAGE == "database":
        row = rate_limit_repository.get(identifier)
        if row is None:
            return config.RATELIMIT_WINDOW_SECONDS
        elapsed = _now() - row["window_started_at"].timestamp()
    else:
        with _memory_lock:
            entry = _memory_store.get(identifier)
            if entry is None:
                return config.RATELIMIT_WINDOW_SECONDS
            elapsed = _now() - entry["window_started_at"]
    remaining = config.RATELIMIT_WINDOW_SECONDS - elapsed
    return max(0, int(remaining))
