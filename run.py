"""Development server launcher.

    python run.py

Boots Flask's built-in server with debug/reload enabled. For production use
`wsgi.py` with Waitress or Gunicorn instead — never this.
"""

from app import app
from config import config

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=not config.IS_PRODUCTION,
    )
