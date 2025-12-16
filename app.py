"""Minimal CS50x Flask starter app."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, render_template, request


# SQLite database file path (local file, no extra services needed).
DB_PATH = Path("library.db")
# Flat daily fine rate (₹) applied only when a book is returned after the due date.
FINE_RATE = 5

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
    search = request.args.get("search", "").strip()
    order_by_options = {
        "title": "title COLLATE NOCASE ASC",
        # When sorting by availability, put the most available first.
        "available_copies": "available_copies DESC, title COLLATE NOCASE ASC",
    }

    order_by = order_by_options.get(sort, order_by_options["title"])
    if sort not in order_by_options:
        sort = "title"  # Keep template state in sync with the default.

    # Optional case-insensitive search on title or author using LIKE.
    # We use parameter binding to avoid interpolation and keep things safe.
    query = "SELECT id, title, author, isbn, total_copies, available_copies FROM books"
    params = []
    if search:
        query += " WHERE LOWER(title) LIKE LOWER(?) OR LOWER(author) LIKE LOWER(?)"
        pattern = f"%{search}%"
        params.extend([pattern, pattern])

    query += f" ORDER BY {order_by}"

    with get_db_connection() as conn:
        books = conn.execute(query, params).fetchall()

    return render_template("books.html", books=books, sort=sort, search=search)


@app.route("/return", methods=["GET", "POST"])
def return_book():
    """Handle book returns and compute any late fines."""
    error = None
    success = None
    today = datetime.now().date()

    def calculate_fine(due_date_str: str) -> tuple[int, int]:
        """Return (days_late, fine_amount) based on due date and today's date."""
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        days_late = max((today - due_date).days, 0)
        fine_amount = days_late * FINE_RATE
        return days_late, fine_amount

    with get_db_connection() as conn:
        def fetch_active_loans():
            # Only include active loans (not yet returned) so users cannot return twice.
            rows = conn.execute(
                """
                SELECT loans.id, loans.book_id, loans.due_date, loans.borrow_date,
                       users.name AS user_name, users.email AS user_email,
                       books.title AS book_title
                FROM loans
                JOIN users ON loans.user_id = users.id
                JOIN books ON loans.book_id = books.id
                WHERE loans.return_date IS NULL
                ORDER BY loans.due_date ASC
                """
            ).fetchall()

            enriched = []
            for row in rows:
                days_late, fine_amount = calculate_fine(row["due_date"])
                enriched.append(
                    {
                        "id": row["id"],
                        "book_id": row["book_id"],
                        "book_title": row["book_title"],
                        "user_name": row["user_name"],
                        "user_email": row["user_email"],
                        "due_date": row["due_date"],
                        "days_late": days_late,
                        "fine": fine_amount,
                    }
                )
            return enriched

        active_loans = fetch_active_loans()

        if request.method == "POST":
            loan_id_raw = request.form.get("loan_id", "").strip()

            if not loan_id_raw:
                error = "Please select a loan to return."
            else:
                try:
                    loan_id = int(loan_id_raw)
                except ValueError:
                    error = "Invalid loan selection."

            if error is None:
                # Ensure the loan is still active before updating anything.
                loan_row = conn.execute(
                    "SELECT id, book_id, due_date FROM loans WHERE id = ? AND return_date IS NULL",
                    (loan_id,),
                ).fetchone()

                if not loan_row:
                    error = "That loan is not active or does not exist."

            if error is None:
                # Compute fine at return time; do not store it in the database.
                days_late, fine_amount = calculate_fine(loan_row["due_date"])

                conn.execute(
                    "UPDATE loans SET return_date = ? WHERE id = ?",
                    (today.strftime("%Y-%m-%d"), loan_id),
                )
                conn.execute(
                    "UPDATE books SET available_copies = available_copies + 1 WHERE id = ?",
                    (loan_row["book_id"],),
                )

                if fine_amount > 0:
                    success = f"Book returned. Fine due: ₹{fine_amount} ({days_late} days late)."
                else:
                    success = "Book returned. No fine due."

                # Refresh active loans list after the return.
                active_loans = fetch_active_loans()

    return render_template(
        "return.html",
        active_loans=active_loans,
        error=error,
        success=success,
        fine_rate=FINE_RATE,
    )


@app.route("/loans")
def list_loans():
    """Show all active loans with live fine calculation and joined details."""
    today = datetime.now().date()

    def calculate_fine(due_date_str: str) -> tuple[int, int]:
        """Return (days_late, fine_amount) based on due date and today's date."""
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        days_late = max((today - due_date).days, 0)
        fine_amount = days_late * FINE_RATE
        return days_late, fine_amount

    with get_db_connection() as conn:
        # Join loans to users and books to display human-friendly info alongside loan dates.
        rows = conn.execute(
            """
            SELECT loans.id, loans.borrow_date, loans.due_date, loans.return_date,
                   users.name AS user_name, books.title AS book_title
            FROM loans
            JOIN users ON loans.user_id = users.id
            JOIN books ON loans.book_id = books.id
            WHERE loans.return_date IS NULL
            ORDER BY loans.due_date ASC
            """
        ).fetchall()

    loans = []
    for row in rows:
        days_late, fine_amount = calculate_fine(row["due_date"])
        loans.append(
            {
                "id": row["id"],
                "user_name": row["user_name"],
                "book_title": row["book_title"],
                "borrow_date": row["borrow_date"],
                "due_date": row["due_date"],
                "days_late": days_late,
                "fine": fine_amount,
            }
        )

    return render_template("loans.html", loans=loans, fine_rate=FINE_RATE)


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
