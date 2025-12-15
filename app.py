"""Minimal CS50x Flask starter app."""
import sqlite3
from pathlib import Path

from flask import Flask, render_template, request


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


@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    """Allow adding a book with simple CS50-style validation."""
    error = None
    success = None

    # Keep form data around to re-render the form after validation errors.
    form_data = {
        "title": request.form.get("title", "").strip(),
        "author": request.form.get("author", "").strip(),
        "isbn": request.form.get("isbn", "").strip(),
        "total_copies": request.form.get("total_copies", "").strip(),
    }

    if request.method == "POST":
        # Basic presence checks: every field is required so records stay complete.
        if not all(form_data.values()):
            error = "All fields are required."
        else:
            # total_copies must be a positive integer so inventory counts are sensible.
            try:
                total_copies_int = int(form_data["total_copies"])
            except ValueError:
                error = "Total copies must be a number."
            else:
                if total_copies_int <= 0:
                    error = "Total copies must be greater than zero."

        if error is None:
            try:
                with get_db_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO books (title, author, isbn, total_copies, available_copies)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            form_data["title"],
                            form_data["author"],
                            form_data["isbn"],
                            total_copies_int,
                            total_copies_int,
                        ),
                    )
                success = "Book added successfully."
                # Reset form fields after successful insert.
                form_data = {"title": "", "author": "", "isbn": "", "total_copies": ""}
            except sqlite3.IntegrityError:
                # ISBN is UNIQUE so duplicates are blocked at the database level.
                error = "A book with that ISBN already exists."

    return render_template("add_book.html", error=error, success=success, form_data=form_data)


@app.route("/books")
def list_books():
    """List all books with simple sorting options."""
    # Whitelist sort options to keep SQL predictable and safe.
    sort = request.args.get("sort", "title")
    order_by_options = {
        "title": "title COLLATE NOCASE ASC",
        # When sorting by availability, put the most available first.
        "available_copies": "available_copies DESC, title COLLATE NOCASE ASC",
    }

    order_by = order_by_options.get(sort, order_by_options["title"])
    if sort not in order_by_options:
        sort = "title"  # Keep template state in sync with the default.

    with get_db_connection() as conn:
        books = conn.execute(
            f"SELECT id, title, author, isbn, total_copies, available_copies FROM books ORDER BY {order_by}"
        ).fetchall()

    return render_template("books.html", books=books, sort=sort)


if __name__ == "__main__":
    # Debug mode is convenient for early development; disable before production.
    app.run(debug=True)
