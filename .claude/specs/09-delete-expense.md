# Spec: Delete Expense

## Overview
This feature lets a logged-in user permanently delete one of their own expenses. It replaces the stub `GET /expenses/<id>/delete` route with a proper POST-based confirmation flow: a GET request renders a confirmation page, and a POST request performs the deletion and redirects back to the profile. Ownership is enforced so users cannot delete expenses belonging to others.

## Depends on
- Step 01 — Database Setup (expenses table exists)
- Step 07 — Add Expense (insert_expense, get_expense_by_id in db.py)
- Step 08 — Edit Expense (get_expense_by_id and ownership pattern)

## Routes
- `GET /expenses/<int:expense_id>/delete` — renders a confirmation page for the expense — logged-in only
- `POST /expenses/<int:expense_id>/delete` — performs the deletion and redirects to `/profile` — logged-in only

## Database changes
No database changes. The existing `expenses` table is sufficient.

## Templates
- **Create:** `templates/delete_expense.html` — confirmation page showing expense details (amount, category, date, description) with a confirm-delete button and a cancel link back to `/profile`
- **Modify:** none

## Files to change
- `app.py` — replace the stub `delete_expense` route with the GET/POST implementation; import `delete_expense` from `database/db.py`
- `database/db.py` — add `delete_expense(expense_id, user_id)` helper

## Files to create
- `templates/delete_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders — never f-strings in SQL)
- The DELETE query must include `WHERE id = ? AND user_id = ?` so a user can never delete another user's expense
- Use `abort(404)` if the expense does not exist; `abort(403)` if it belongs to a different user
- Use `POST` for the destructive action — the GET only shows the confirmation page
- Flash a success message after deletion: `"Expense deleted."`
- All templates extend `base.html`
- Use CSS variables — never hardcode hex values
- Use `url_for()` for every internal link — never hardcode URLs

## Definition of done
- [ ] Visiting `GET /expenses/<id>/delete` while logged in shows a confirmation page with the expense's amount, category, date, and description
- [ ] The confirmation page has a "Delete" button (POST form) and a "Cancel" link that returns to `/profile`
- [ ] Submitting the confirmation form deletes the expense from the database and redirects to `/profile` with the flash message "Expense deleted."
- [ ] Visiting the route while logged out redirects to `/login`
- [ ] Trying to delete another user's expense returns 403
- [ ] Trying to delete a non-existent expense returns 404
- [ ] After deletion the expense no longer appears in the profile transaction list
