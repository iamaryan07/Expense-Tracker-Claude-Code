# Spec: Registration

## Overview
This step wires up the registration form so new users can create a Spendly account. The `GET /register` route already renders the form; this step adds the `POST /register` handler that validates input, hashes the password, inserts the new user into the database, and redirects on success. It is the first step that writes user-supplied data to the database and establishes the pattern every subsequent auth route will follow.

## Depends on
- Step 1 (Database Setup) — `get_db()`, `init_db()`, and the `users` table must exist.

## Routes
- `POST /register` — accepts registration form data, creates a new user, redirects to `/login` — public

## Database changes
No new tables or columns. The existing `users` table (`id`, `name`, `email`, `password_hash`, `created_at`) is sufficient.

## Templates
- **Modify:** `templates/register.html` — add `method="POST"` and `action="{{ url_for('register_post') }}"` (or `action="{{ url_for('register') }}"` if both verbs share the same endpoint name) to the `<form>` tag; add `name` attributes to all inputs; display flash error messages at the top of the form.

## Files to change
- `app.py` — add `POST /register` route (and required Flask imports: `request`, `redirect`, `url_for`, `flash`, `session`)
- `database/db.py` — add `create_user(name, email, password)` helper
- `templates/register.html` — wire up the form as described above

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.generate_password_hash` is already available.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never use f-strings or `%` formatting in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash` — never store plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use `abort(400)` for bad requests, not bare string returns
- Flash messages for validation errors (blank fields, duplicate email) via Flask's `flash()` + `get_flashed_messages()`
- On duplicate email, show a user-friendly error — do not expose raw SQLite exceptions
- `app.secret_key` must be set for `flash()` to work — add it to `app.py` if missing
- After successful registration, redirect to `/login` with a success flash message

## Definition of done
- [ ] Submitting the form with valid data creates a new row in `users` with a hashed password
- [ ] Submitting with a blank name, email, or password shows an inline error and does not insert a row
- [ ] Submitting with an already-registered email shows an error message ("Email already in use" or similar)
- [ ] Successful registration redirects to `/login`
- [ ] Password is never stored as plaintext — `password_hash` column contains a `pbkdf2:sha256:…` string
- [ ] All form field values (except password) are preserved in the form on validation failure
- [ ] `GET /register` still renders the empty form without errors
- [ ] App starts without errors and no existing routes are broken
