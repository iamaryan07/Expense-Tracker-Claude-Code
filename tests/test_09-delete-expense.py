"""
Tests for Spec 09 — Delete Expense

Covers:
- Unit: delete_expense removes the correct row from the DB
- Unit: delete_expense does not remove a row owned by a different user
- GET /expenses/<id>/delete unauthenticated → 302 /login
- POST /expenses/<id>/delete unauthenticated → 302 /login
- GET non-existent id → 404
- POST non-existent id → 404
- GET expense owned by another user → 403
- POST expense owned by another user → 403
- POST another user's expense does not alter the DB row
- GET authenticated owner → 200, confirmation page with expense details
- Confirmation page shows expense amount
- Confirmation page shows expense category
- Confirmation page shows expense date
- Confirmation page shows expense description
- Confirmation page has a POST form (delete button)
- Confirmation page has a cancel link pointing to /profile
- POST valid deletion → 302 /profile
- POST valid deletion flashes "Expense deleted."
- After POST the expense row is gone from the DB
- After POST other users' rows are unaffected
- SQL injection via expense id URL is handled safely (Flask int converter)
- SQL injection via description in DB does not corrupt table after delete

Fixture approach:
- Patch database.db.DB_PATH to a per-test temp file via patch.object
- client_with_db yields (flask_test_client, owner_user_id, db_path)
- _login_session injects user_id into Flask session directly
- _insert_expense inserts a controlled row and returns its integer id
- _fetch_expense_by_id fetches a single expense row by id (or None)
"""

import os
import tempfile
import pytest
from unittest.mock import patch

import database.db as db_module
from app import app
from database.db import init_db, create_user, get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PAST_DATE = "2026-03-20"   # safe past date (before today 2026-05-30)


def _create_test_user(name="Test User", email="testuser@example.com",
                      password="password123"):
    """Create a user and return their integer id."""
    create_user(name, email, password)
    conn = db_module.get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return row["id"]


def _login_session(client, user_id):
    """Inject user_id into the Flask session without going through the login form."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _insert_expense(user_id, amount=100.0, category="Food",
                    date=PAST_DATE, description="Test expense"):
    """Insert an expense row directly and return its id."""
    conn = db_module.get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description),
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id


def _fetch_expense_by_id(expense_id):
    """Return the expense row for the given id (or None if deleted/missing)."""
    conn = db_module.get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    conn.close()
    return row


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_db():
    """
    Yields (flask_test_client, owner_user_id, tmp_db_path).

    A fresh temp-file SQLite DB is created per test so each test starts
    with an empty schema and only its own controlled rows.
    """
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    with patch.object(db_module, "DB_PATH", db_path):
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret"

        with app.test_client() as client:
            with app.app_context():
                init_db()
            user_id = _create_test_user()
            yield client, user_id, db_path

    os.unlink(db_path)


# ---------------------------------------------------------------------------
# Unit tests — delete_expense helper
# ---------------------------------------------------------------------------

class TestDeleteExpenseUnit:
    def test_delete_expense_removes_row_from_db(self, client_with_db):
        """delete_expense called with matching expense_id and user_id must remove the row."""
        _, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        from database.db import delete_expense
        delete_expense(expense_id, user_id)
        row = _fetch_expense_by_id(expense_id)
        assert row is None

    def test_delete_expense_does_not_remove_row_for_wrong_user(self, client_with_db):
        """delete_expense called with a mismatched user_id must leave the row intact."""
        _, user_id, _ = client_with_db
        other_id = _create_test_user(name="Other User", email="other@example.com")
        expense_id = _insert_expense(other_id)
        from database.db import delete_expense
        # Attempt deletion as wrong user — must be a no-op
        delete_expense(expense_id, user_id)
        row = _fetch_expense_by_id(expense_id)
        assert row is not None

    def test_delete_expense_does_not_affect_other_rows(self, client_with_db):
        """Deleting one expense must leave sibling rows owned by the same user untouched."""
        _, user_id, _ = client_with_db
        id_to_delete = _insert_expense(user_id, description="Delete me")
        id_to_keep = _insert_expense(user_id, description="Keep me")
        from database.db import delete_expense
        delete_expense(id_to_delete, user_id)
        row = _fetch_expense_by_id(id_to_keep)
        assert row is not None

    def test_delete_expense_on_nonexistent_id_does_not_raise(self, client_with_db):
        """delete_expense on an id that does not exist must not raise an exception."""
        _, user_id, _ = client_with_db
        from database.db import delete_expense
        # Should execute cleanly — zero rows affected, no error
        delete_expense(99999, user_id)


# ---------------------------------------------------------------------------
# GET /expenses/<id>/delete — unauthenticated
# ---------------------------------------------------------------------------

class TestGetDeleteExpenseUnauthenticated:
    def test_get_delete_expense_without_session_returns_302(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        resp = client.get(f"/expenses/{expense_id}/delete", follow_redirects=False)
        assert resp.status_code == 302

    def test_get_delete_expense_without_session_redirects_to_login(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        resp = client.get(f"/expenses/{expense_id}/delete", follow_redirects=False)
        assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# POST /expenses/<id>/delete — unauthenticated
# ---------------------------------------------------------------------------

class TestPostDeleteExpenseUnauthenticated:
    def test_post_delete_expense_without_session_returns_302(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        resp = client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)
        assert resp.status_code == 302

    def test_post_delete_expense_without_session_redirects_to_login(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        resp = client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)
        assert "/login" in resp.headers["Location"]

    def test_post_delete_expense_without_session_does_not_delete_row(self, client_with_db):
        """An unauthenticated POST must not delete the expense row."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)
        row = _fetch_expense_by_id(expense_id)
        assert row is not None


# ---------------------------------------------------------------------------
# 404 — non-existent expense id
# ---------------------------------------------------------------------------

class TestDeleteExpenseNotFound:
    def test_get_nonexistent_expense_returns_404(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/99999/delete")
        assert resp.status_code == 404

    def test_post_nonexistent_expense_returns_404(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/99999/delete")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 403 — authenticated user deleting someone else's expense
# ---------------------------------------------------------------------------

class TestDeleteExpenseForbidden:
    def test_get_other_users_expense_returns_403(self, client_with_db):
        client, logged_in_id, _ = client_with_db
        other_id = _create_test_user(name="Other User", email="other@example.com")
        expense_id = _insert_expense(other_id)
        _login_session(client, logged_in_id)
        resp = client.get(f"/expenses/{expense_id}/delete")
        assert resp.status_code == 403

    def test_post_other_users_expense_returns_403(self, client_with_db):
        client, logged_in_id, _ = client_with_db
        other_id = _create_test_user(name="Other User", email="other@example.com")
        expense_id = _insert_expense(other_id)
        _login_session(client, logged_in_id)
        resp = client.post(f"/expenses/{expense_id}/delete")
        assert resp.status_code == 403

    def test_post_other_users_expense_does_not_delete_row(self, client_with_db):
        """A 403 response must leave the expense row in the DB."""
        client, logged_in_id, _ = client_with_db
        other_id = _create_test_user(name="Other User", email="other@example.com")
        expense_id = _insert_expense(other_id, description="Must survive")
        _login_session(client, logged_in_id)
        client.post(f"/expenses/{expense_id}/delete")
        row = _fetch_expense_by_id(expense_id)
        assert row is not None
        assert row["description"] == "Must survive"


# ---------------------------------------------------------------------------
# GET /expenses/<id>/delete — authenticated owner (confirmation page)
# ---------------------------------------------------------------------------

class TestGetDeleteExpenseConfirmationPage:
    def test_get_delete_expense_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/delete")
        assert resp.status_code == 200

    def test_get_delete_expense_shows_expense_amount(self, client_with_db):
        """Confirmation page must display the expense amount."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, amount=249.99)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/delete")
        assert b"249.99" in resp.data

    def test_get_delete_expense_shows_expense_category(self, client_with_db):
        """Confirmation page must display the expense category."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, category="Entertainment")
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/delete")
        assert b"Entertainment" in resp.data

    def test_get_delete_expense_shows_expense_date(self, client_with_db):
        """Confirmation page must display the expense date."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, date="2026-02-14")
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/delete")
        assert b"2026-02-14" in resp.data

    def test_get_delete_expense_shows_expense_description(self, client_with_db):
        """Confirmation page must display the expense description."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, description="Valentine dinner")
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/delete")
        assert b"Valentine dinner" in resp.data

    def test_get_delete_expense_has_post_form(self, client_with_db):
        """Confirmation page must contain a form with method POST."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/delete")
        html = resp.data.decode().lower()
        assert "<form" in html
        assert 'method="post"' in html or "method='post'" in html

    def test_get_delete_expense_form_action_contains_expense_id(self, client_with_db):
        """The POST form action must target this expense's delete URL."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/delete")
        html = resp.data.decode()
        assert f"/expenses/{expense_id}/delete" in html

    def test_get_delete_expense_has_cancel_link_to_profile(self, client_with_db):
        """Confirmation page must have a cancel link pointing to /profile."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/delete")
        html = resp.data.decode()
        assert "/profile" in html

    def test_get_delete_expense_has_cancel_link_text(self, client_with_db):
        """The cancel link must be discoverable by label text."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/delete")
        html = resp.data.decode().lower()
        assert "cancel" in html


# ---------------------------------------------------------------------------
# POST /expenses/<id>/delete — happy path (deletion confirmed)
# ---------------------------------------------------------------------------

class TestPostDeleteExpenseHappyPath:
    def test_post_delete_expense_returns_302(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)
        assert resp.status_code == 302

    def test_post_delete_expense_redirects_to_profile(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)
        assert "/profile" in resp.headers["Location"]

    def test_post_delete_expense_flashes_success_message(self, client_with_db):
        """A successful deletion must flash exactly 'Expense deleted.'"""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/delete", follow_redirects=True
        )
        assert b"Expense deleted." in resp.data

    def test_post_delete_expense_row_gone_from_db(self, client_with_db):
        """After a confirmed POST the expense must no longer exist in the DB."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        client.post(f"/expenses/{expense_id}/delete")
        row = _fetch_expense_by_id(expense_id)
        assert row is None

    def test_post_delete_expense_does_not_remove_other_users_rows(self, client_with_db):
        """Deleting one user's expense must not affect expenses owned by another user."""
        client, user_id, _ = client_with_db
        other_id = _create_test_user(name="Other User", email="other@example.com")
        other_expense_id = _insert_expense(other_id, description="Other user's expense")
        expense_id = _insert_expense(user_id, description="My expense to delete")
        _login_session(client, user_id)
        client.post(f"/expenses/{expense_id}/delete")
        surviving_row = _fetch_expense_by_id(other_expense_id)
        assert surviving_row is not None

    def test_post_delete_expense_does_not_remove_sibling_row(self, client_with_db):
        """Deleting one expense must leave the same user's other expenses intact."""
        client, user_id, _ = client_with_db
        id_to_delete = _insert_expense(user_id, description="Delete me")
        id_to_keep = _insert_expense(user_id, description="Keep me")
        _login_session(client, user_id)
        client.post(f"/expenses/{id_to_delete}/delete")
        row = _fetch_expense_by_id(id_to_keep)
        assert row is not None

    def test_post_delete_expense_removed_from_profile_transaction_list(self, client_with_db):
        """After deletion the expense must not appear in the /profile transaction list."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, description="Unique marker ZYXWVU")
        _login_session(client, user_id)
        client.post(f"/expenses/{expense_id}/delete")
        resp = client.get("/profile")
        assert b"Unique marker ZYXWVU" not in resp.data


# ---------------------------------------------------------------------------
# SQL injection safety
# ---------------------------------------------------------------------------

class TestSqlInjectionSafety:
    def test_sql_injection_via_non_integer_id_returns_404(self, client_with_db):
        """Flask's <int:expense_id> converter must reject non-integer paths."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/'; DROP TABLE expenses; --/delete")
        # Flask route converter will not match — 404 is the expected outcome
        assert resp.status_code == 404

    def test_sql_injection_via_non_integer_post_returns_404(self, client_with_db):
        """Flask's <int:expense_id> converter must reject non-integer paths on POST too."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/'; DROP TABLE expenses; --/delete")
        assert resp.status_code == 404

    def test_delete_does_not_corrupt_expenses_table(self, client_with_db):
        """After a normal deletion the expenses table must still be queryable."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        client.post(f"/expenses/{expense_id}/delete")
        conn = db_module.get_db()
        rows = conn.execute("SELECT * FROM expenses").fetchall()
        conn.close()
        assert isinstance(rows, list)
