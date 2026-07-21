"""The background worker that actually delivers queued emails.

Per the spec's own design note: "run a simple loop/thread on app startup
that polls `email_outbox` for `pending` rows, attempts SMTP delivery, and
marks each `sent` or `failed`." Started once from `app.py` as a daemon
thread -- it never blocks a request, and it never prevents the process
from exiting (`daemon=True`).

Two separate ways this must never crash the app, both by design rather
than by luck:
  1. `config.NOTIFICATION_WORKER_ENABLED=false` -- the thread is simply
     never started (see `start()`); email_outbox rows just accumulate as
     'pending' forever, which is harmless.
  2. `config.SMTP_HOST` is blank (not configured) -- each poll cycle
     no-ops instead of trying (and failing) to connect; see `_poll_once()`.
  3. An SMTP error while a mail server *is* configured -- caught per
     message in `_send_one()`, which marks that one row 'failed' and moves
     on to the next; one bad row never stops the loop or the process.
"""

import smtplib
import threading
import time
from email.message import EmailMessage

from config import config
from repositories import email_outbox_repository

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _send_one(row: dict) -> bool:
    """Attempt delivery of one outbox row. Returns True on success. Never
    raises -- any SMTP/network error is caught here and treated as a
    delivery failure for this row only."""
    try:
        message = EmailMessage()
        message["Subject"] = row["subject"]
        message["From"] = config.SMTP_FROM_EMAIL
        message["To"] = row["to_email"]
        message.set_content(row["body"])

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as smtp:
            if config.SMTP_USE_TLS:
                smtp.starttls()
            if config.SMTP_USERNAME:
                smtp.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except Exception:
        return False


def _poll_once() -> None:
    if not config.SMTP_HOST:
        # Not configured -- nothing to attempt this cycle. Rows stay
        # 'pending' until an operator sets SMTP_HOST, at which point the
        # backlog drains on the next poll.
        return

    for row in email_outbox_repository.list_pending():
        if _send_one(row):
            email_outbox_repository.mark_sent(row["id"])
        else:
            email_outbox_repository.mark_failed(row["id"])


def _run() -> None:
    while not _stop_event.is_set():
        try:
            _poll_once()
        except Exception:
            # A transient DB error (or anything else unexpected) must not
            # kill the worker thread permanently -- it just tries again
            # next cycle.
            pass
        _stop_event.wait(config.NOTIFICATION_WORKER_INTERVAL_SECONDS)


def start() -> None:
    """Start the background thread, unless it's disabled or already
    running. Safe to call more than once (e.g. accidentally from a
    reloader) -- a second call is a no-op."""
    global _worker_thread

    if not config.NOTIFICATION_WORKER_ENABLED:
        return
    if _worker_thread is not None and _worker_thread.is_alive():
        return

    _stop_event.clear()
    _worker_thread = threading.Thread(target=_run, name="notification-worker", daemon=True)
    _worker_thread.start()


def stop() -> None:
    """Signal the worker to stop after its current sleep. Used by the test
    harness; a running production process normally just exits instead."""
    _stop_event.set()
