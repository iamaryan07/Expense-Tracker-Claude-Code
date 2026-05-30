# Spec: Backend Routes for Profile Page

## Overview
This feature replaces all hardcoded stub data in the `/profile` route with real database queries. Step 4 built the full profile UI using static Python dicts; Step 5 wires those same template variables to live SQLite data — fetching the authenticated user's record, computing aggregate stats, pulling recent transactions, and summarising spending by category. No new routes or tables are needed; the work is entirely in `database/db.py` (new query helpers) and `app.py` (replacing hardcoded dicts with helper calls).

## Depends on
- Step 1: Database setup (`users` and `expenses` tables must exist)
- Step 2: Registration (real user records must be in the DB)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 4: Profile page design (the `profile.html` template and its expected context variables)

## Routes
- `GET /profile` — already exists; modify the view function to fetch real data — logged-in only

No new routes.

## Database changes
No new tables or columns. All required data is already in `users` and `expenses`.

## Templates
- **Modify:** `templates/profile.html` — no structural changes; the template already uses the variables `user`, `stats`, `transactions`, and `categories`. The only change needed is verifying that `member_since` is rendered from `user["member_since"]` and that amount formatting matches what the helpers return.

## Files to change
- `app.py` — replace hardcoded `user`, `stats`, `transactions`, and `categories` dicts in the `/profile` route with calls to new helpers from `database/db.py`
- `database/db.py` — add four new query helpers:
  - `get_user_by_id(user_id)` — fetch a single user row by primary key
  - `get_expense_stats(user_id)` — return total spent, transaction count, and top category for the user
  - `get_recent_transactions(user_id, limit=5)` — return the most recent expenses, newest first
  - `get_category_breakdown(user_id)` — return per-category totals and percentage of total spending, sorted by amount descending

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw sqlite3 via `get_db()` only
- Parameterised queries only — never f-strings or string concatenation in SQL
- Passwords hashed with werkzeug — no auth changes in this step
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `get_user_by_id` must return `None` if the user does not exist; the route must `abort(404)` in that case
- Amount formatting (e.g. `₹1,200.00`) must be done in Python, not in the template — pass pre-formatted strings so the template stays logic-free
- `member_since` must be derived from `users.created_at` and formatted as `"Month YYYY"` (e.g. `"January 2025"`)
- `initials` must be computed from the user's `name` field (first letter of each word, max 2 letters, uppercased)
- Category percentage must be computed as `round(category_amount / total_spent * 100)` — integer, not float
- All DB connections must be closed after use (no context managers needed, just explicit `.close()`)

## Definition of done
- [ ] Visiting `/profile` while logged in returns HTTP 200 and shows the real user's name and email from the DB
- [ ] `member_since` on the profile page reflects the actual `created_at` date from the `users` table
- [ ] Summary stats (total spent, transaction count, top category) match the actual expenses for that user in the DB
- [ ] The transaction history table shows real rows from the `expenses` table, newest first
- [ ] The category breakdown shows real per-category totals and correct percentages that sum to ~100%
- [ ] Logging in as a different user shows that user's own data (not Demo User's data)
- [ ] Visiting `/profile` without a session redirects to `/login`
- [ ] No hardcoded data remains in the `/profile` route in `app.py`
- [ ] All SQL queries in `database/db.py` use `?` placeholders — no f-strings in SQL
