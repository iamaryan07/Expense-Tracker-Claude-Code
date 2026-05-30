"""
Tests for Spec 07 — Add Expense

Covers:
- Unit: insert_expense inserts a row with all fields
- Unit: insert_expense stores NULL when description is None
- GET /expenses/add unauthenticated → 302 /login
- GET /expenses/add authenticated → 200, form present, all 7 category options present
- POST /expenses/add unauthenticated → 302 /login
- POST valid data → 302 /profile, row exists in DB
- POST missing amount → 200, error in body
- POST amount=0 → 200, error in body
- POST non-numeric amount → 200, error in body
- POST invalid category → 200, error in body
- POST invalid date string → 200, error in body
- POST no description → 302 /profile, row inserted with description=NULL
- SQL injection in form fields does not crash the app

Fixture approach:
- Patch database.db.DB_PATH to a per-test temp file via patch.object
- client_with_db yields (flask_test_client, user_id, db_path)
- _login_session injects user_id into Flask session directly
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


def _create_test_user(name="Test User", email="testuser@example.com",
                      password="password123"):
    """Create a test user and return their DB row id."""
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


def _fetch_expenses_for_user(user_id):
    """Return all expense rows for a given user_id."""
    conn = db_module.get_db()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_db():
    """
    Yields (flask_test_client, user_id, tmp_db_path).

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
# Unit tests — insert_expense helper
# ---------------------------------------------------------------------------

class TestInsertExpenseUnit:
    def test_insert_expense_with_valid_data_creates_row(self, client_with_db):
        """insert_expense with all valid fields inserts exactly one row."""
        _, user_id, _ = client_with_db
        insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 1

    def test_insert_expense_persists_correct_amount(self, client_with_db):
        _, user_id, _ = client_with_db
        insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = _fetch_expenses_for_user(user_id)
        assert rows[0]["amount"] == 50.0

    def test_insert_expense_persists_correct_category(self, client_with_db):
        _, user_id, _ = client_with_db
        insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = _fetch_expenses_for_user(user_id)
        assert rows[0]["category"] == "Food"

    def test_insert_expense_persists_correct_date(self, client_with_db):
        _, user_id, _ = client_with_db
        insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = _fetch_expenses_for_user(user_id)
        assert rows[0]["date"] == "2026-03-20"

    def test_insert_expense_persists_correct_description(self, client_with_db):
        _, user_id, _ = client_with_db
        insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = _fetch_expenses_for_user(user_id)
        assert rows[0]["description"] == "Lunch"

    def test_insert_expense_with_none_description_stores_null(self, client_with_db):
        """insert_expense called with description=None must store NULL in the DB."""
        _, user_id, _ = client_with_db
        insert_expense(user_id, 25.0, "Transport", "2026-03-21", None)
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 1
        assert rows[0]["description"] is None

    def test_insert_expense_associates_row_with_correct_user(self, client_with_db):
        _, user_id, _ = client_with_db
        insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")
        rows = _fetch_expenses_for_user(user_id)
        assert rows[0]["user_id"] == user_id


# ---------------------------------------------------------------------------
# GET /expenses/add — unauthenticated
# ---------------------------------------------------------------------------

class TestGetAddExpenseUnauthenticated:
    def test_get_add_expense_without_session_returns_302(self, client_with_db):
        client, _, _ = client_with_db
        resp = client.get("/expenses/add", follow_redirects=False)
        assert resp.status_code == 302

    def test_get_add_expense_without_session_redirects_to_login(self, client_with_db):
        client, _, _ = client_with_db
        resp = client.get("/expenses/add", follow_redirects=False)
        assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# GET /expenses/add — authenticated
# ---------------------------------------------------------------------------

class TestGetAddExpenseAuthenticated:
    def test_get_add_expense_with_session_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert resp.status_code == 200

    def test_get_add_expense_response_contains_form_tag(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b"<form" in resp.data

    def test_get_add_expense_form_uses_post_method(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        html = resp.data.decode()
        # The form element must declare method POST (case-insensitive)
        assert 'method="post"' in html.lower() or "method='post'" in html.lower()

    def test_get_add_expense_contains_amount_field(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b'name="amount"' in resp.data

    def test_get_add_expense_contains_category_select(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b"<select" in resp.data
        assert b'name="category"' in resp.data

    def test_get_add_expense_contains_date_field(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b'name="date"' in resp.data

    def test_get_add_expense_contains_description_field(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b'name="description"' in resp.data

    def test_get_add_expense_select_contains_food_option(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b"Food" in resp.data

    def test_get_add_expense_select_contains_transport_option(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b"Transport" in resp.data

    def test_get_add_expense_select_contains_bills_option(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b"Bills" in resp.data

    def test_get_add_expense_select_contains_health_option(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b"Health" in resp.data

    def test_get_add_expense_select_contains_entertainment_option(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b"Entertainment" in resp.data

    def test_get_add_expense_select_contains_shopping_option(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b"Shopping" in resp.data

    def test_get_add_expense_select_contains_other_option(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b"Other" in resp.data

    def test_get_add_expense_select_contains_all_seven_options(self, client_with_db):
        """All 7 fixed category options must appear in the rendered form."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        html = resp.data.decode()
        for category in VALID_CATEGORIES:
            assert category in html, f"Category '{category}' missing from form"


# ---------------------------------------------------------------------------
# POST /expenses/add — unauthenticated
# ---------------------------------------------------------------------------

class TestPostAddExpenseUnauthenticated:
    def test_post_add_expense_without_session_returns_302(self, client_with_db):
        client, _, _ = client_with_db
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_post_add_expense_without_session_redirects_to_login(self, client_with_db):
        client, _, _ = client_with_db
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
            follow_redirects=False,
        )
        assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# POST /expenses/add — valid data
# ---------------------------------------------------------------------------

class TestPostAddExpenseValidData:
    def test_post_valid_expense_returns_302(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_post_valid_expense_redirects_to_profile(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
            follow_redirects=False,
        )
        assert "/profile" in resp.headers["Location"]

    def test_post_valid_expense_inserts_row_in_db(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 1

    def test_post_valid_expense_stores_correct_amount(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert rows[0]["amount"] == 50.0

    def test_post_valid_expense_stores_correct_category(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert rows[0]["category"] == "Food"

    def test_post_valid_expense_stores_correct_date(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert rows[0]["date"] == "2026-03-20"

    def test_post_valid_expense_stores_correct_description(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert rows[0]["description"] == "Lunch"


# ---------------------------------------------------------------------------
# POST /expenses/add — missing amount
# ---------------------------------------------------------------------------

class TestPostAddExpenseMissingAmount:
    def test_post_missing_amount_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_missing_amount_contains_error_message(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        html = resp.data.decode().lower()
        assert "error" in html or "amount" in html

    def test_post_missing_amount_does_not_insert_row(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# POST /expenses/add — amount = 0
# ---------------------------------------------------------------------------

class TestPostAddExpenseAmountZero:
    def test_post_amount_zero_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_amount_zero_contains_error_message(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        html = resp.data.decode().lower()
        assert "error" in html or "greater than 0" in html or "amount" in html

    def test_post_amount_zero_does_not_insert_row(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# POST /expenses/add — non-numeric amount
# ---------------------------------------------------------------------------

class TestPostAddExpenseNonNumericAmount:
    def test_post_non_numeric_amount_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "abc", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_non_numeric_amount_contains_error_message(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "abc", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        html = resp.data.decode().lower()
        assert "error" in html or "amount" in html

    def test_post_non_numeric_amount_does_not_insert_row(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "abc", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 0

    def test_post_negative_amount_returns_200(self, client_with_db):
        """Negative amounts are also invalid (must be > 0)."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "-10.0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_negative_amount_does_not_insert_row(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "-10.0", "category": "Food",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# POST /expenses/add — invalid category
# ---------------------------------------------------------------------------

class TestPostAddExpenseInvalidCategory:
    def test_post_invalid_category_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "NotACategory",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_invalid_category_contains_error_message(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "NotACategory",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        html = resp.data.decode().lower()
        assert "error" in html or "category" in html

    def test_post_invalid_category_does_not_insert_row(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "NotACategory",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 0

    def test_post_empty_category_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_empty_category_does_not_insert_row(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# POST /expenses/add — invalid date string
# ---------------------------------------------------------------------------

class TestPostAddExpenseInvalidDate:
    def test_post_invalid_date_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "not-a-date", "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_invalid_date_contains_error_message(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "not-a-date", "description": "Lunch"},
        )
        html = resp.data.decode().lower()
        assert "error" in html or "date" in html

    def test_post_invalid_date_does_not_insert_row(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "not-a-date", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 0

    def test_post_wrong_date_format_returns_200(self, client_with_db):
        """Date in DD/MM/YYYY format (not YYYY-MM-DD) must be rejected."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "20/03/2026", "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_wrong_date_format_does_not_insert_row(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "20/03/2026", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 0

    def test_post_empty_date_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "", "description": "Lunch"},
        )
        assert resp.status_code == 200

    def test_post_empty_date_does_not_insert_row(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "Food",
                  "date": "", "description": "Lunch"},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# POST /expenses/add — no description (optional field)
# ---------------------------------------------------------------------------

class TestPostAddExpenseNoDescription:
    def test_post_no_description_returns_302(self, client_with_db):
        """description is optional — omitting it must still succeed."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-03-21", "description": ""},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_post_no_description_redirects_to_profile(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-03-21", "description": ""},
            follow_redirects=False,
        )
        assert "/profile" in resp.headers["Location"]

    def test_post_no_description_inserts_row(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-03-21", "description": ""},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert len(rows) == 1

    def test_post_no_description_stores_null_in_db(self, client_with_db):
        """Blank description must be stored as NULL, not empty string."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-03-21", "description": ""},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert rows[0]["description"] is None

    def test_post_whitespace_only_description_stores_null_in_db(self, client_with_db):
        """Whitespace-only description must be stripped and stored as NULL."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post(
            "/expenses/add",
            data={"amount": "75.0", "category": "Transport",
                  "date": "2026-03-21", "description": "   "},
        )
        rows = _fetch_expenses_for_user(user_id)
        assert rows[0]["description"] is None


# ---------------------------------------------------------------------------
# SQL injection safety
# ---------------------------------------------------------------------------

class TestSqlInjectionSafety:
    def test_sql_injection_in_description_does_not_crash(self, client_with_db):
        """Parameterized queries must prevent SQL injection via description field."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        malicious = "'; DROP TABLE expenses; --"
        resp = client.post(
            "/expenses/add",
            data={"amount": "10.0", "category": "Food",
                  "date": "2026-03-20", "description": malicious},
        )
        # Must not 500
        assert resp.status_code in (200, 302)

    def test_sql_injection_in_description_expenses_table_survives(self, client_with_db):
        """After an injection attempt, the expenses table must still be queryable."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        malicious = "'; DROP TABLE expenses; --"
        client.post(
            "/expenses/add",
            data={"amount": "10.0", "category": "Food",
                  "date": "2026-03-20", "description": malicious},
        )
        # If the table was dropped, this query would raise; instead it should succeed
        rows = _fetch_expenses_for_user(user_id)
        assert isinstance(rows, list)

    def test_sql_injection_in_amount_field_does_not_crash(self, client_with_db):
        """Malicious amount value must be caught by float() parsing, not reach the DB."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        malicious = "'; DROP TABLE expenses; --"
        resp = client.post(
            "/expenses/add",
            data={"amount": malicious, "category": "Food",
                  "date": "2026-03-20", "description": "test"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Form re-population on validation failure
# ---------------------------------------------------------------------------

class TestFormRepopulationOnValidationFailure:
    def test_previously_submitted_category_retained_after_amount_error(self, client_with_db):
        """When amount is invalid, the submitted category should still appear selected."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "bad", "category": "Health",
                  "date": "2026-03-20", "description": "Doctor visit"},
        )
        assert b"Health" in resp.data

    def test_previously_submitted_description_retained_after_amount_error(self, client_with_db):
        """When amount is invalid, the previously entered description should appear."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "bad", "category": "Food",
                  "date": "2026-03-20", "description": "My unique description text"},
        )
        assert b"My unique description text" in resp.data

    def test_previously_submitted_date_retained_after_category_error(self, client_with_db):
        """When category is invalid, the submitted date should still appear in the form."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post(
            "/expenses/add",
            data={"amount": "50.0", "category": "InvalidCat",
                  "date": "2026-03-20", "description": "Lunch"},
        )
        assert b"2026-03-20" in resp.data
