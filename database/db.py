import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'spendly.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL NOT NULL,
            category    TEXT NOT NULL,
            date        TEXT NOT NULL,
            description TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def seed_db():
    init_db()
    conn = get_db()

    conn.execute(
        "INSERT OR IGNORE INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo1234")),
    )
    conn.commit()

    user = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
    ).fetchone()
    user_id = user["id"]

    sample_expenses = [
        (user_id, 450.00,  "Food",          "2025-05-01", "Grocery run at DMart"),
        (user_id, 120.00,  "Transport",     "2025-05-03", "Metro card recharge"),
        (user_id, 1200.00, "Bills",         "2025-05-05", "Electricity bill"),
        (user_id, 350.00,  "Health",        "2025-05-08", "Pharmacy — vitamins"),
        (user_id, 599.00,  "Entertainment", "2025-05-10", "Netflix subscription"),
        (user_id, 2300.00, "Shopping",      "2025-05-14", "New headphones"),
        (user_id, 80.00,   "Food",          "2025-05-17", "Coffee and snacks"),
        (user_id, 500.00,  "Other",         "2025-05-20", "Birthday gift"),
    ]

    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        sample_expenses,
    )
    conn.commit()
    conn.close()


def create_user(name, email, password):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password)),
    )
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return user


def get_expense_stats(user_id, start_date=None, end_date=None):
    conn = get_db()
    date_clause = ""
    p1 = [user_id]
    if start_date and end_date:
        date_clause = " AND date BETWEEN ? AND ?"
        p1 += [start_date, end_date]
    row = conn.execute(
        "SELECT SUM(amount) AS total, COUNT(*) AS cnt FROM expenses WHERE user_id = ?" + date_clause,
        p1
    ).fetchone()
    top = conn.execute(
        "SELECT category, SUM(amount) AS s FROM expenses"
        " WHERE user_id = ?" + date_clause + " GROUP BY category ORDER BY s DESC LIMIT 1",
        p1
    ).fetchone()
    conn.close()
    total = row["total"] or 0.0
    return {
        "total_spent": f"₹{total:,.2f}",
        "transaction_count": row["cnt"],
        "top_category": top["category"] if top else "—",
    }


def get_recent_transactions(user_id, limit=5, start_date=None, end_date=None):
    conn = get_db()
    date_clause = ""
    params = [user_id]
    if start_date and end_date:
        date_clause = " AND date BETWEEN ? AND ?"
        params += [start_date, end_date]
    params.append(limit)
    rows = conn.execute(
        "SELECT date, description, category, amount"
        " FROM expenses WHERE user_id = ?" + date_clause +
        " ORDER BY date DESC, id DESC LIMIT ?",
        params
    ).fetchall()
    conn.close()
    return [
        {
            "date": r["date"],
            "description": r["description"],
            "category": r["category"],
            "amount": f"₹{r['amount']:,.2f}",
        }
        for r in rows
    ]


def get_category_breakdown(user_id, start_date=None, end_date=None):
    conn = get_db()
    date_clause = ""
    params = [user_id]
    if start_date and end_date:
        date_clause = " AND date BETWEEN ? AND ?"
        params += [start_date, end_date]
    rows = conn.execute(
        "SELECT category, SUM(amount) AS s FROM expenses"
        " WHERE user_id = ?" + date_clause + " GROUP BY category ORDER BY s DESC",
        params
    ).fetchall()
    conn.close()
    total = sum(r["s"] for r in rows) or 1
    return [
        {
            "name": r["category"],
            "amount": f"₹{r['s']:,.2f}",
            "pct": round(r["s"] / total * 100),
        }
        for r in rows
    ]


def insert_expense(user_id, amount, category, date, description):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description),
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id
