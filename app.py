"""Minimal CS50x Flask starter app."""
import sqlite3
from datetime import datetime, timedelta
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


@app.route("/add_user", methods=["GET", "POST"])
def add_user():
    """Allow registering a user with straightforward validation."""
    error = None
    success = None

    # Preserve form input so users do not need to retype after errors.
    form_data = {
        "name": request.form.get("name", "").strip(),
        "email": request.form.get("email", "").strip(),
    }

    if request.method == "POST":
        # Require both fields so user records stay complete.
        if not all(form_data.values()):
            error = "Name and email are required."

        if error is None:
            try:
                with get_db_connection() as conn:
                    conn.execute(
                        "INSERT INTO users (name, email) VALUES (?, ?)",
                        (form_data["name"], form_data["email"]),
                    )
                success = "User registered successfully."
                form_data = {"name": "", "email": ""}
            except sqlite3.IntegrityError:
                # Email is UNIQUE; surface a clear message instead of a stack trace.
                error = "A user with that email already exists."

    return render_template("add_user.html", error=error, success=success, form_data=form_data)


@app.route("/users")
def list_users():
    """List all registered users in a simple table."""
    # Stable alphabetical ordering keeps the list predictable for users and tests.
    with get_db_connection() as conn:
        users = conn.execute(
            "SELECT id, name, email FROM users ORDER BY name COLLATE NOCASE ASC"
        ).fetchall()

    return render_template("users.html", users=users)


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


@app.route("/borrow", methods=["GET", "POST"])
def borrow():
    """Allow users to borrow books with inventory and duplicate checks."""
    error = None
    success = None

    with get_db_connection() as conn:
        # Always fetch users and available books for the form dropdowns.
        users = conn.execute(
            "SELECT id, name, email FROM users ORDER BY name COLLATE NOCASE ASC"
        ).fetchall()

        # Only show books that actually have copies available to borrow.
        available_books = conn.execute(
            """
            SELECT id, title, author, available_copies 
            FROM books 
            WHERE available_copies > 0 
            ORDER BY title COLLATE NOCASE ASC
            """
        ).fetchall()

        if request.method == "POST":
            user_id = request.form.get("user_id", "").strip()
            book_id = request.form.get("book_id", "").strip()

            # Both selections are required so we can record who borrowed what.
            if not user_id or not book_id:
                error = "Please select both a user and a book."
            else:
                try:
                    user_id = int(user_id)
                    book_id = int(book_id)
                except ValueError:
                    error = "Invalid user or book selection."

            if error is None:
                # Double-check that the book still has available copies (race condition guard).
                book = conn.execute(
                    "SELECT available_copies FROM books WHERE id = ?", (book_id,)
                ).fetchone()

                if not book or book["available_copies"] <= 0:
                    error = "This book is no longer available."

            if error is None:
                # Prevent the same user from borrowing the same book multiple times without returning.
                existing_loan = conn.execute(
                    """
                    SELECT id FROM loans 
                    WHERE user_id = ? AND book_id = ? AND return_date IS NULL
                    """,
                    (user_id, book_id),
                ).fetchone()

                if existing_loan:
                    error = "This user has already borrowed this book and not returned it yet."

            if error is None:
                # Calculate borrow and due dates (14-day loan period).
                borrow_date = datetime.now().strftime("%Y-%m-%d")
                due_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

                # Record the loan and decrement available inventory atomically.
                conn.execute(
                    """
                    INSERT INTO loans (user_id, book_id, borrow_date, due_date, return_date)
                    VALUES (?, ?, ?, ?, NULL)
                    """,
                    (user_id, book_id, borrow_date, due_date),
                )
                conn.execute(
                    "UPDATE books SET available_copies = available_copies - 1 WHERE id = ?",
                    (book_id,),
                )
                success = "Book borrowed successfully. Due date: " + due_date

    return render_template(
        "borrow.html",
        users=users,
        available_books=available_books,
        error=error,
        success=success,
    )


if __name__ == "__main__":
    # Debug mode is convenient for early development; disable before production.
    app.run(debug=True)
