# Library Management System (Flask + SQLite)

A lightweight, production-friendly library management starter built with Flask and SQLite. It covers adding books/users, borrowing/returning with inventory tracking, dynamic fines, and simple listings.

## Features
- Add and list books with availability tracking (total vs. available copies).
- Add and list users with unique email enforcement.
- Borrow books: prevents duplicate active loans, sets due date (+14 days), decrements availability.
- Return books: marks return date, increments availability, computes fines on the fly (₹5/day late).
- View active loans with live fine calculation and overdue indication.
- Search and sort books (by title or availability).

## Project structure
- `app.py` — Flask app, routes, and database helpers.
- `schema.sql` — Database schema (books, users, loans) with foreign keys.
- `templates/` — Jinja templates (`layout`, `index`, `add_book`, `add_user`, `books`, `users`, `borrow`, `return`, `loans`).
- `static/styles.css` — Minimal styling.

## Setup
1) Install dependencies (Flask, sqlite3 is built-in):
```bash
pip install flask
```

2) Initialize the database:
```bash
sqlite3 library.db < schema.sql
```

3) Run the app (dev server):
```bash
python app.py
```
Visit http://127.0.0.1:5000/

## Usage overview
- Add books: `/add_book`
- Add users: `/add_user`
- Borrow a book: `/borrow` (only shows books with available copies; blocks duplicate active loans per user/book)
- Return a book: `/return` (only active loans; fine computed dynamically)
- View books: `/books` (search `?search=term`, sort `?sort=title|available_copies`)
- View users: `/users`
- View active loans: `/loans`

## Notes on data model
- Three tables separate concerns: books (inventory), users (patrons), loans (history + active checkouts).
- `available_copies` is stored to keep inventory updates O(1) instead of recalculating from loans each time.
- Fines are **not stored**; they’re derived from `due_date` vs. today to avoid stale values.
- Foreign keys are defined in schema; ensure `PRAGMA foreign_keys = ON;` is applied (included in `schema.sql`).

## Next steps (optional)
- Add auth for admin actions.
- Add edit/delete flows with safety checks (no active loans).
- Add pagination on `/books` and `/users` for large datasets.
- Add tests (helpers and route flows) using an in-memory SQLite database.

## Author
Built by **Abhinav Ravi Shankar**

## License
MIT
