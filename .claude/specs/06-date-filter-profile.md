# Spec: Date Filter for Profile Page

## Overview
This feature adds a date-range filter to the profile page so users can narrow
the expense stats, recent transactions, and category breakdown to a specific
time window. Instead of always showing all-time data, users can pick a preset
(This Month, Last Month, Last 3 Months, All Time) or supply a custom start/end
date. The filter is applied server-side by passing query-string parameters to
the existing `/profile` route, keeping the architecture simple and testable.

## Depends on
- Step 01 — Database setup (expenses table exists)
- Step 02 — Registration
- Step 03 — Login / Logout (session-based auth)
- Step 04 — Profile page design (profile.html template exists)
- Step 05 — Backend routes for profile (DB helpers exist)

## Routes
- `GET /profile?preset=<value>&start=<YYYY-MM-DD>&end=<YYYY-MM-DD>` — same
  profile route, now accepts optional filter params — logged-in only

No new routes.

## Database changes
No database changes. Filtering is done by adding `WHERE date BETWEEN ? AND ?`
clauses to the existing queries in `database/db.py`.

## Templates
- **Modify:** `templates/profile.html`
  - Add a filter bar above the stats section with:
    - Preset buttons/links: This Month, Last Month, Last 3 Months, All Time
    - A custom date range form with two `<input type="date">` fields and a
      Filter button
    - Active preset visually highlighted
    - Display the active date range as a human-readable label
      (e.g. "May 2026" or "01 Mar – 30 May 2026")

## Files to change
- `app.py` — parse `preset`, `start`, `end` query params in `/profile`;
  compute date range; pass `start_date`, `end_date`, and `active_preset` to
  DB helpers and template
- `database/db.py` — update `get_expense_stats`, `get_recent_transactions`,
  and `get_category_breakdown` to accept optional `start_date` / `end_date`
  parameters and apply a `BETWEEN` filter when provided
- `templates/profile.html` — add filter UI (see Templates section)
- `static/css/style.css` — add styles for the filter bar, preset buttons,
  and active state

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never interpolate dates into SQL strings
- Passwords hashed with werkzeug (unchanged — just don't break auth)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Preset logic must live in `app.py`, not in the template
- Date arithmetic must use Python's `datetime` / `date` stdlib only
- The `start` and `end` query params must be validated as valid `YYYY-MM-DD`
  dates; invalid values fall back to the "All Time" preset silently
- The filter must not break the page when the user has zero expenses
- Preset `this-month` defaults to the first and last day of the current month
- Preset `last-month` defaults to the first and last day of the previous month
- Preset `last-3-months` defaults to 3 months ago (same day) through today
- Preset `all-time` (or no params) applies no date filter — returns all rows
- DB helpers must remain backwards-compatible (default `None` for both date
  params so existing callers without date args still work)

## Definition of done
- [ ] Visiting `/profile` with no query params shows all-time data (unchanged
  behaviour)
- [ ] Clicking "This Month" reloads the page and stats/transactions/categories
  reflect only expenses dated in the current calendar month
- [ ] Clicking "Last Month" shows only last month's expenses
- [ ] Clicking "Last 3 Months" shows expenses from 3 months ago through today
- [ ] Clicking "All Time" resets to showing all expenses
- [ ] Submitting the custom date form with a valid start and end date filters
  data to that exact range (inclusive)
- [ ] Submitting an invalid date (e.g. `start=not-a-date`) falls back
  gracefully to all-time data without a 500 error
- [ ] The active preset button is visually distinct from the inactive ones
- [ ] The active date range is displayed as a human-readable label on the page
- [ ] The page renders correctly when the filtered result set is empty (no
  transactions, stats show ₹0.00 / 0 transactions)
- [ ] All stats, recent transactions, and category breakdown all respect the
  same active filter simultaneously
