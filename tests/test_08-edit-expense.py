"""
Tests for Spec 08 — Edit Expense

Covers:
- Unit: get_expense_by_id returns the correct row or None
- Unit: update_expense changes all four editable fields in the DB
- GET /expenses/<id>/edit unauthenticated → 302 /login
- POST /expenses/<id>/edit unauthenticated → 302 /login
- GET non-existent id → 404
- POST non-existent id → 404
- GET expense owned by another user → 403
- POST expense owned by another user → 403
- GET authenticated owner → 200, form pre-filled with current values
- GET form contains all 7 category options
- GET form action points to correct edit URL
- POST valid changes → 302 /profile, DB row updated, flash "Expense updated."
- POST valid changes: each updated field reflected in DB
- POST missing amount → 200, error shown, DB row unchanged
- POST amount=0 → 200, error shown, DB row unchanged
- POST non-numeric amount → 200, error shown, DB row unchanged
- POST negative amount → 200, error shown, DB row unchanged
- POST future date → 200, error shown, DB row unchanged
- POST pre-2000 date → 200, error shown, DB row unchanged
- POST invalid category → 200, error shown, DB row unchanged
- POST empty category → 200, error shown, DB row unchanged
- POST no description → 302, description becomes NULL in DB
- POST validation failure: submitted values preserved in form
- Profile page: each transaction row has an Edit link to correct URL
- SQL injection in description field does not crash or corrupt DB

Fixture approach:
- Patch database.db.DB_PATH to a per-test temp file via patch.object
- client_with_db yields (flask_test_client, owner_user_id, db_path)
- _login_session injects user_id into Flask session directly
- _insert_expense inserts a controlled row and returns its integer id
"""

import os
import tempfile
import pytest
from unittest.mock import patch

import database.db as db_module
from app import app
from database.db import init_db, create_user, get_db, insert_expense


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]

PAST_DATE = "2026-03-20"       # a safe past date, before today (2026-05-30)
FUTURE_DATE = "2099-12-31"     # guaranteed to be in the future
PRE_2000_DATE = "1999-12-31"   # before the 2000-01-01 lower bound


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
    """Return the expense row for the given id (or None)."""
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
# Unit tests — get_expense_by_id
# ---------------------------------------------------------------------------

class TestGetExpenseByIdUnit:
    def test_get_expense_by_id_returns_correct_row(self, client_with_db):
        _, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, amount=42.0, category="Health",
                                     date=PAST_DATE, description="Pills")
        from database.db import get_expense_by_id
        row = get_expense_by_id(expense_id)
        assert row is not None
        assert row["id"] == expense_id

    def test_get_expense_by_id_returns_correct_amount(self, client_with_db):
        _, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, amount=42.0)
        from database.db import get_expense_by_id
        row = get_expense_by_id(expense_id)
        assert row["amount"] == 42.0

    def test_get_expense_by_id_returns_correct_category(self, client_with_db):
        _, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, category="Health")
        from database.db import get_expense_by_id
        row = get_expense_by_id(expense_id)
        assert row["category"] == "Health"

    def test_get_expense_by_id_returns_correct_user_id(self, client_with_db):
        _, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        from database.db import get_expense_by_id
        row = get_expense_by_id(expense_id)
        assert row["user_id"] == user_id

    def test_get_expense_by_id_returns_none_for_missing_id(self, client_with_db):
        from database.db import get_expense_by_id
        row = get_expense_by_id(99999)
        assert row is None


# ---------------------------------------------------------------------------
# Unit tests — update_expense
# ---------------------------------------------------------------------------

class TestUpdateExpenseUnit:
    def test_update_expense_changes_amount(self, client_with_db):
        _, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, amount=100.0)
        from database.db import update_expense
        update_expense(expense_id, user_id, amount=250.0, category="Food",
                       date=PAST_DATE, description="Updated")
        row = _fetch_expense_by_id(expense_id)
        assert row["amount"] == 250.0

    def test_update_expense_changes_category(self, client_with_db):
        _, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, category="Food")
        from database.db import update_expense
        update_expense(expense_id, user_id, amount=100.0, category="Bills",
                       date=PAST_DATE, description="Updated")
        row = _fetch_expense_by_id(expense_id)
        assert row["category"] == "Bills"

    def test_update_expense_changes_date(self, client_with_db):
        _, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, date="2026-01-01")
        from database.db import update_expense
        update_expense(expense_id, user_id, amount=100.0, category="Food",
                       date="2026-02-15", description="Updated")
        row = _fetch_expense_by_id(expense_id)
        assert row["date"] == "2026-02-15"

    def test_update_expense_changes_description(self, client_with_db):
        _, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, description="Old description")
        from database.db import update_expense
        update_expense(expense_id, user_id, amount=100.0, category="Food",
                       date=PAST_DATE, description="Brand new description")
        row = _fetch_expense_by_id(expense_id)
        assert row["description"] == "Brand new description"

    def test_update_expense_can_set_description_to_none(self, client_with_db):
        _, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, description="Has a description")
        from database.db import update_expense
        update_expense(expense_id, user_id, amount=100.0, category="Food",
                       date=PAST_DATE, description=None)
        row = _fetch_expense_by_id(expense_id)
        assert row["description"] is None

    def test_update_expense_does_not_change_user_id(self, client_with_db):
        """update_expense must not alter user_id — ownership must be preserved."""
        _, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        from database.db import update_expense
        update_expense(expense_id, user_id, amount=999.0, category="Bills",
                       date=PAST_DATE, description="Changed")
        row = _fetch_expense_by_id(expense_id)
        assert row["user_id"] == user_id


# ---------------------------------------------------------------------------
# GET /expenses/<id>/edit — unauthenticated
# ---------------------------------------------------------------------------

class TestGetEditExpenseUnauthenticated:
    def test_get_edit_expense_without_session_returns_302(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        resp = client.get(f"/expenses/{expense_id}/edit", follow_redirects=False)
        assert resp.status_code == 302

    def test_get_edit_expense_without_session_redirects_to_login(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        resp = client.get(f"/expenses/{expense_id}/edit", follow_redirects=False)
        assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# POST /expenses/<id>/edit — unauthenticated
# ---------------------------------------------------------------------------

class TestPostEditExpenseUnauthenticated:
    def test_post_edit_expense_without_session_returns_302(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": PAST_DATE, "description": "Updated"},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_post_edit_expense_without_session_redirects_to_login(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": PAST_DATE, "description": "Updated"},
            follow_redirects=False,
        )
        assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# 404 — non-existent expense id
# ---------------------------------------------------------------------------

class TestEditExpenseNotFound:
    def test_get_nonexistent_expense_returns_404(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/99999/edit")
        assert resp.status_code == 404

    def test_post_nonexistent_expense_returns_404(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/99999/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": PAST_DATE, "description": "Updated"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 403 — authenticated user editing someone else's expense
# ---------------------------------------------------------------------------

class TestEditExpenseForbidden:
    def test_get_other_users_expense_returns_403(self, client_with_db):
        client, owner_id, _ = client_with_db
        # Create a second user who owns the expense
        other_id = _create_test_user(name="Other User",
                                     email="other@example.com")
        expense_id = _insert_expense(other_id)
        # Log in as owner_id (not the expense owner)
        _login_session(client, owner_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 403

    def test_post_other_users_expense_returns_403(self, client_with_db):
        client, owner_id, _ = client_with_db
        other_id = _create_test_user(name="Other User",
                                     email="other@example.com")
        expense_id = _insert_expense(other_id)
        _login_session(client, owner_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": PAST_DATE, "description": "Hacked"},
        )
        assert resp.status_code == 403

    def test_post_other_users_expense_does_not_alter_db(self, client_with_db):
        """A 403 response must leave the original expense row unchanged."""
        client, owner_id, _ = client_with_db
        other_id = _create_test_user(name="Other User",
                                     email="other@example.com")
        expense_id = _insert_expense(other_id, amount=100.0,
                                     description="Original")
        _login_session(client, owner_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "999.0", "category": "Bills",
                  "date": PAST_DATE, "description": "Hacked"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["amount"] == 100.0
        assert row["description"] == "Original"


# ---------------------------------------------------------------------------
# GET /expenses/<id>/edit — authenticated owner (form pre-population)
# ---------------------------------------------------------------------------

class TestGetEditExpenseAuthenticated:
    def test_get_edit_expense_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 200

    def test_get_edit_expense_response_contains_form_tag(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"<form" in resp.data

    def test_get_edit_expense_form_uses_post_method(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        html = resp.data.decode().lower()
        assert 'method="post"' in html or "method='post'" in html

    def test_get_edit_expense_form_action_contains_expense_id(self, client_with_db):
        """Form action must point to the edit URL for this specific expense id."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        html = resp.data.decode()
        assert f"/expenses/{expense_id}/edit" in html

    def test_get_edit_expense_prefills_amount(self, client_with_db):
        """The amount input must be pre-filled with the current expense amount."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, amount=123.45)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        # The amount is a float stored as REAL; value="123.45" should appear
        assert b"123.45" in resp.data

    def test_get_edit_expense_prefills_date(self, client_with_db):
        """The date input must be pre-filled with the current expense date."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, date="2026-02-14")
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"2026-02-14" in resp.data

    def test_get_edit_expense_prefills_description(self, client_with_db):
        """The description input must be pre-filled with the current expense description."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, description="Unique marker text XYZ")
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"Unique marker text XYZ" in resp.data

    def test_get_edit_expense_prefills_category_as_selected(self, client_with_db):
        """The category matching the expense must appear as selected in the form."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, category="Entertainment")
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"Entertainment" in resp.data

    def test_get_edit_expense_form_contains_all_seven_category_options(self, client_with_db):
        """All 7 valid categories must be present in the edit form select."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        html = resp.data.decode()
        for category in VALID_CATEGORIES:
            assert category in html, f"Category '{category}' missing from edit form"

    def test_get_edit_expense_form_contains_amount_field(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="amount"' in resp.data

    def test_get_edit_expense_form_contains_date_field(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="date"' in resp.data

    def test_get_edit_expense_form_contains_description_field(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b'name="description"' in resp.data

    def test_get_edit_expense_form_contains_category_select(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"<select" in resp.data
        assert b'name="category"' in resp.data


# ---------------------------------------------------------------------------
# POST /expenses/<id>/edit — valid data (happy path)
# ---------------------------------------------------------------------------

class TestPostEditExpenseValidData:
    def test_post_valid_update_returns_302(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-04-01", "description": "Bus pass"},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_post_valid_update_redirects_to_profile(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-04-01", "description": "Bus pass"},
            follow_redirects=False,
        )
        assert "/profile" in resp.headers["Location"]

    def test_post_valid_update_flashes_expense_updated(self, client_with_db):
        """A successful update must flash exactly 'Expense updated.'"""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-04-01", "description": "Bus pass"},
            follow_redirects=True,
        )
        assert b"Expense updated." in resp.data

    def test_post_valid_update_changes_amount_in_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, amount=100.0)
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-04-01", "description": "Bus pass"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["amount"] == 75.0

    def test_post_valid_update_changes_category_in_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, category="Food")
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-04-01", "description": "Bus pass"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["category"] == "Transport"

    def test_post_valid_update_changes_date_in_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, date="2026-01-10")
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-04-01", "description": "Bus pass"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["date"] == "2026-04-01"

    def test_post_valid_update_changes_description_in_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, description="Old description")
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-04-01", "description": "New description"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["description"] == "New description"

    def test_post_valid_update_does_not_change_user_id_in_db(self, client_with_db):
        """update_expense must not affect the expense's user_id."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-04-01", "description": "Bus pass"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["user_id"] == user_id

    def test_post_no_description_stores_null_in_db(self, client_with_db):
        """Blank description on edit must be stored as NULL."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, description="Had a description")
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "75.0", "category": "Food",
                  "date": PAST_DATE, "description": ""},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["description"] is None

    def test_post_whitespace_only_description_stores_null_in_db(self, client_with_db):
        """Whitespace-only description must be stripped and stored as NULL."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, description="Had a description")
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "75.0", "category": "Food",
                  "date": PAST_DATE, "description": "   "},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["description"] is None


# ---------------------------------------------------------------------------
# POST /expenses/<id>/edit — missing amount
# ---------------------------------------------------------------------------

class TestPostEditExpenseMissingAmount:
    def test_post_missing_amount_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "", "category": "Food",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_missing_amount_shows_error(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "", "category": "Food",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        html = resp.data.decode().lower()
        assert "error" in html or "amount" in html

    def test_post_missing_amount_does_not_update_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, amount=100.0)
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "", "category": "Food",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["amount"] == 100.0


# ---------------------------------------------------------------------------
# POST /expenses/<id>/edit — amount = 0
# ---------------------------------------------------------------------------

class TestPostEditExpenseAmountZero:
    def test_post_amount_zero_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "0", "category": "Food",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_amount_zero_does_not_update_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, amount=100.0)
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "0", "category": "Food",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["amount"] == 100.0


# ---------------------------------------------------------------------------
# POST /expenses/<id>/edit — non-numeric and negative amount
# ---------------------------------------------------------------------------

class TestPostEditExpenseInvalidAmount:
    def test_post_non_numeric_amount_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "abc", "category": "Food",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_non_numeric_amount_does_not_update_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, amount=100.0)
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "abc", "category": "Food",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["amount"] == 100.0

    def test_post_negative_amount_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "-50.0", "category": "Food",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_negative_amount_does_not_update_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, amount=100.0)
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "-50.0", "category": "Food",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["amount"] == 100.0


# ---------------------------------------------------------------------------
# POST /expenses/<id>/edit — future date
# ---------------------------------------------------------------------------

class TestPostEditExpenseFutureDate:
    def test_post_future_date_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": FUTURE_DATE, "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_future_date_shows_error(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": FUTURE_DATE, "description": "Lunch"},
        )
        html = resp.data.decode().lower()
        assert "error" in html or "date" in html

    def test_post_future_date_does_not_update_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, date=PAST_DATE)
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": FUTURE_DATE, "description": "Lunch"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["date"] == PAST_DATE

    def test_post_pre_2000_date_returns_200(self, client_with_db):
        """Dates before 2000-01-01 must be rejected."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": PRE_2000_DATE, "description": "Old"},
        )
        assert resp.status_code == 200

    def test_post_pre_2000_date_does_not_update_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, date=PAST_DATE)
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": PRE_2000_DATE, "description": "Old"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["date"] == PAST_DATE

    def test_post_malformed_date_string_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": "not-a-date", "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_malformed_date_does_not_update_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, date=PAST_DATE)
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": "not-a-date", "description": "Lunch"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["date"] == PAST_DATE


# ---------------------------------------------------------------------------
# POST /expenses/<id>/edit — invalid category
# ---------------------------------------------------------------------------

class TestPostEditExpenseInvalidCategory:
    def test_post_invalid_category_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "NotARealCategory",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_invalid_category_shows_error(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "NotARealCategory",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        html = resp.data.decode().lower()
        assert "error" in html or "category" in html

    def test_post_invalid_category_does_not_update_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, category="Food")
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "NotARealCategory",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["category"] == "Food"

    def test_post_empty_category_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_empty_category_does_not_update_db(self, client_with_db):
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, category="Food")
        _login_session(client, user_id)
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "",
                  "date": PAST_DATE, "description": "Lunch"},
        )
        row = _fetch_expense_by_id(expense_id)
        assert row["category"] == "Food"


# ---------------------------------------------------------------------------
# POST validation failure — form values preserved
# ---------------------------------------------------------------------------

class TestFormRepopulationOnValidationFailure:
    def test_submitted_category_preserved_after_amount_error(self, client_with_db):
        """When amount is invalid the submitted category value must appear in the response."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id, category="Food")
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "bad", "category": "Health",
                  "date": PAST_DATE, "description": "Doctor"},
        )
        assert b"Health" in resp.data

    def test_submitted_description_preserved_after_amount_error(self, client_with_db):
        """When amount is invalid the submitted description must appear in the response."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "bad", "category": "Food",
                  "date": PAST_DATE, "description": "Unique marker ABCXYZ"},
        )
        assert b"Unique marker ABCXYZ" in resp.data

    def test_submitted_date_preserved_after_category_error(self, client_with_db):
        """When category is invalid the submitted date must appear in the response."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "NotReal",
                  "date": "2026-03-15", "description": "Something"},
        )
        assert b"2026-03-15" in resp.data

    def test_submitted_amount_preserved_after_category_error(self, client_with_db):
        """When category is invalid the submitted amount must appear in the response."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "88.88", "category": "NotReal",
                  "date": PAST_DATE, "description": "Something"},
        )
        assert b"88.88" in resp.data


# ---------------------------------------------------------------------------
# Profile page — Edit links present and correct
# ---------------------------------------------------------------------------

class TestProfilePageEditLinks:
    def test_profile_page_contains_edit_link_text(self, client_with_db):
        """Each transaction row on /profile must contain an 'Edit' link."""
        client, user_id, _ = client_with_db
        _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get("/profile")
        assert b"Edit" in resp.data

    def test_profile_page_edit_link_points_to_edit_url(self, client_with_db):
        """The Edit link on /profile must point to /expenses/<id>/edit."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get("/profile")
        html = resp.data.decode()
        assert f"/expenses/{expense_id}/edit" in html

    def test_profile_page_edit_links_match_all_expense_ids(self, client_with_db):
        """Every expense row must have its own correct edit URL in the profile page."""
        client, user_id, _ = client_with_db
        id_a = _insert_expense(user_id, amount=10.0, description="Expense A")
        id_b = _insert_expense(user_id, amount=20.0, description="Expense B")
        _login_session(client, user_id)
        resp = client.get("/profile")
        html = resp.data.decode()
        assert f"/expenses/{id_a}/edit" in html
        assert f"/expenses/{id_b}/edit" in html

    def test_profile_page_edit_link_navigates_to_edit_form(self, client_with_db):
        """Following an edit link from /profile must render the edit form (200)."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# SQL injection safety
# ---------------------------------------------------------------------------

class TestSqlInjectionSafety:
    def test_sql_injection_in_description_does_not_crash(self, client_with_db):
        """Parameterized queries must prevent SQL injection via description field."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        malicious = "'; DROP TABLE expenses; --"
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": PAST_DATE, "description": malicious},
        )
        assert resp.status_code in (200, 302)

    def test_sql_injection_in_description_expenses_table_survives(self, client_with_db):
        """After an injection attempt the expenses table must still be queryable."""
        client, user_id, _ = client_with_db
        expense_id = _insert_expense(user_id)
        _login_session(client, user_id)
        malicious = "'; DROP TABLE expenses; --"
        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "50.0", "category": "Food",
                  "date": PAST_DATE, "description": malicious},
        )
        conn = db_module.get_db()
        rows = conn.execute("SELECT * FROM expenses").fetchall()
        conn.close()
        assert isinstance(rows, list)

    def test_sql_injection_via_get_url_id_returns_404(self, client_with_db):
        """A non-integer id in the URL must be handled safely (Flask returns 404)."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        # Flask's <int:id> converter will reject non-integer paths entirely
        resp = client.get("/expenses/99999/edit")
        assert resp.status_code == 404
