# Spec: Login and Logout

## Overview
This step implements the login and logout flows, completing the authentication cycle started in Step 2. `POST /login` validates credentials, starts a Flask session on success, and redirects to the dashboard (or a stub). `GET /logout` clears the session and redirects to the landing page. Together these two routes mean every subsequent step can gate pages behind a real session check.

## Depends on
- Step 1 (Database Setup) — `get_db()` and the `users` table must exist.
- Step 2 (Registration) — `create_user()` and the hashed-password pattern must be in place.

## Routes
- `POST /login` — accepts email + password, verifies credentials, sets `session["user_id"]`, redirects to `/profile` — public
- `GET /logout` — clears the session, redirects to `/` — logged-in (no hard guard yet, but should be harmless if called when already logged out)

## Database changes
No database changes. The existing `users` table with `id`, `email`, and `password_hash` is sufficient.

## Templates
- **Modify:** `templates/login.html` — add `method="POST"` and `action="{{ url_for('login') }}"` to the `<form>` tag; add `name` attributes to email and password inputs; display flash messages at the top of the form.
- **Modify:** `templates/base.html` — add a "Logout" link (visible only when `session.user_id` is set) and a "Login" / "Register" link pair (visible when logged out).

## Files to change
- `app.py` — convert `GET /login` to a `GET, POST` route; implement `POST /login` handler; implement `GET /logout` route (replace the stub).
- `database/db.py` — add `get_user_by_email(email)` helper that returns a `sqlite3.Row` or `None`.
- `templates/login.html` — wire up the form as described above.
- `templates/base.html` — add session-aware nav links.

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is already available via the existing `werkzeug` install.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never use f-strings or `%` formatting in SQL
- Use `werkzeug.security.check_password_hash` to verify passwords — never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Store only `session["user_id"]` (the integer PK) — never store the password or full user row in the session
- On failed login, show a generic error ("Invalid email or password") — do not reveal which field is wrong
- Use `session.clear()` in logout, not manual key deletion
- After successful login, redirect to `url_for("profile")`
- After logout, redirect to `url_for("landing")`
- `app.secret_key` is already set — do not change it

## Definition of done
- [ ] Submitting valid credentials sets `session["user_id"]` and redirects to `/profile`
- [ ] Submitting an unknown email shows "Invalid email or password" and does not set a session
- [ ] Submitting a correct email with a wrong password shows "Invalid email or password" and does not set a session
- [ ] Submitting with blank email or password shows a validation error before hitting the DB
- [ ] Email field value is preserved on validation failure; password field is always cleared
- [ ] `GET /logout` clears the session and redirects to `/`
- [ ] Calling `/logout` when already logged out redirects to `/` without error
- [ ] Nav in `base.html` shows "Login / Register" when logged out and "Logout" when logged in
- [ ] `GET /login` still renders the empty form without errors
- [ ] App starts without errors and no existing routes are broken
