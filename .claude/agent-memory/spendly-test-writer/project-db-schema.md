---
name: project-db-schema
description: Spendly DB schema — tables, columns, types, and key constraints
metadata:
  type: project
---

## Tables

### users
| column        | type    | notes                          |
|---------------|---------|--------------------------------|
| id            | INTEGER | PK AUTOINCREMENT               |
| name          | TEXT    | NOT NULL                       |
| email         | TEXT    | NOT NULL UNIQUE                |
| password_hash | TEXT    | NOT NULL (werkzeug hash)       |
| created_at    | TEXT    | DEFAULT datetime('now')        |

### expenses
| column      | type    | notes                              |
|-------------|---------|-------------------------------------|
| id          | INTEGER | PK AUTOINCREMENT                    |
| user_id     | INTEGER | NOT NULL REFERENCES users(id)       |
| amount      | REAL    | NOT NULL                            |
| category    | TEXT    | NOT NULL                            |
| date        | TEXT    | NOT NULL, format YYYY-MM-DD         |
| description | TEXT    | nullable                            |
| created_at  | TEXT    | DEFAULT datetime('now')             |

FK enforcement requires `PRAGMA foreign_keys = ON` — `get_db()` does this on
every connection.

## Key DB helpers (database/db.py)
- `init_db()` — creates tables (IF NOT EXISTS)
- `seed_db()` — inserts demo user + 8 sample expenses (2025-05-xx dates)
- `create_user(name, email, password)` — hashes password, inserts user
- `get_user_by_email(email)` / `get_user_by_id(user_id)` — returns `sqlite3.Row`
- `get_expense_stats(user_id, start_date=None, end_date=None)` → dict with `total_spent`, `transaction_count`, `top_category`
- `get_recent_transactions(user_id, limit=5, start_date=None, end_date=None)` → list of dicts
- `get_category_breakdown(user_id, start_date=None, end_date=None)` → list of dicts with `name`, `amount`, `pct`

All helpers accept optional `start_date`/`end_date` (YYYY-MM-DD strings).
When both are provided a `WHERE date BETWEEN ? AND ?` clause is applied.

**Why:** Needed to write correct DB setup helpers in tests and understand the
data contract that `/profile` tests assert against.
