# Spec: Edit Expense

## Overview
This feature lets a logged-in user edit an existing expense they own. The stub route `GET /expenses/<id>/edit` becomes a full GET + POST handler that pre-fills a form with the current expense data, validates the submission with the same rules used in Step 7 (Add Expense), and updates the record in the database. Editing an expense someone else owns returns 403; editing a non-existent expense returns 404.

## Depends on
- Step 01 — Database setup (expenses table)
- Step 07 — Add Expense (shared `_validate_expense_form` helper and `CATEGORIES` list)

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the expense — logged-in only
- `POST /expenses/<int:id>/edit` — process the updated expense and redirect to profile — logged-in only

## Database changes
No database changes. The existing `expenses` table has all required columns.

A new DB helper is needed in `database/db.py`:
- `get_expense_by_id(expense_id)` — returns the expense row or `None`
- `update_expense(expense_id, amount, category, date, description)` — updates the row in place

## Templates
- **Create:** `templates/edit_expense.html` — edit form, structurally identical to `add_expense.html` but pre-filled and with a "Save changes" button
- **Modify:** `templates/profile.html` — add an Edit link/button on each transaction row that points to `url_for('edit_expense', id=<expense_id>)`

## Files to change
- `app.py` — replace the stub `edit_expense` route with GET + POST implementation
- `database/db.py` — add `get_expense_by_id` and `update_expense` helpers
- `templates/profile.html` — add edit links to transaction rows

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — no f-strings in SQL
- Passwords hashed with werkzeug (not relevant here, but no other crypto introduced)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Authorization: if `expense["user_id"] != session["user_id"]` → `abort(403)`
- If expense not found → `abort(404)`
- Reuse `_validate_expense_form` from `app.py` for POST validation — do not duplicate logic
- After a successful update, redirect to `url_for("profile")` with a flash "Expense updated."
- The edit form must include today's date as the `max` attribute on the date input (same as add form)
- `get_recent_transactions` currently fetches only 5 rows and doesn't expose `id` — update the query to also select `id` so the edit link can be built; increase the limit or remove it so all expenses appear (profile page shows all for the logged-in user)

## Definition of done
- [ ] Navigating to `/expenses/<id>/edit` for an expense owned by the logged-in user renders a form pre-filled with that expense's amount, category, date, and description
- [ ] Submitting valid changes updates the expense and redirects to `/profile` with a "Expense updated." flash message
- [ ] Submitting invalid data (bad amount, future date, unknown category) re-renders the form with an error message and preserves entered values
- [ ] Navigating to `/expenses/<id>/edit` for an expense owned by a different user returns 403
- [ ] Navigating to `/expenses/99999/edit` (non-existent) returns 404
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Each transaction row on `/profile` has a visible Edit link that navigates to the correct edit URL
