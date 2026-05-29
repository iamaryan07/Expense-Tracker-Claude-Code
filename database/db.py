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
