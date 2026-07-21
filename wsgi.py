"""Production WSGI entry point.

Exposes the module-level `app` object for a WSGI server.

Gunicorn (Linux/macOS):
    gunicorn --bind 0.0.0.0:8000 wsgi:app

Waitress (cross-platform, incl. Windows):
    waitress-serve --host=0.0.0.0 --port=8000 wsgi:app

Or run this file directly to serve via Waitress:
    python wsgi.py

Set APP_ENV=production and a strong SECRET_KEY in the environment first; the
app refuses to start otherwise.
"""

from app import app  # noqa: F401 - imported for `wsgi:app` and importing enforces config policy

if __name__ == "__main__":
    from waitress import serve

    serve(app, host="0.0.0.0", port=8000)
