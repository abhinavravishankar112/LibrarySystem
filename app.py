"""Minimal CS50x Flask starter app."""
import sqlite3
from pathlib import Path

from flask import Flask, render_template


# SQLite database file path (local file, no extra services needed).
DB_PATH = Path("library.db")

app = Flask(__name__)


def get_db_connection():
    """Return a new SQLite connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    """Render the homepage."""
    return render_template("index.html")


if __name__ == "__main__":
    # Debug mode is convenient for early development; disable before production.
    app.run(debug=True)
