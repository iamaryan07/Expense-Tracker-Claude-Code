"""
Tests for Spec 07 — Add Expense

Covers:
- Unit: insert_expense stores a row correctly
- Unit: insert_expense with description=None stores NULL
- Route GET unauthenticated → 302 to /login
- Route GET authenticated → 200, form present, 7 category options
- Route POST unauthenticated → 302 to /login
- Route POST valid data → 302 to /profile, row inserted in DB
- Route POST missing amount → 200 + error
- Route POST amount=0 → 200 + error
- Route POST non-numeric amount → 200 + error
- Route POST invalid category → 200 + error
- Route POST invalid date → 200 + error
- Route POST no description → 302, row with description=NULL
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

def _create_test_user_and_get_id(name="Test User", email="test@example.com",
                                  password="password123"):
    create_user(name, email, password)
    conn = db_module.get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row["id"]


def _login_session(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _count_expenses(user_id):
    conn = db_module.get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row["cnt"]


def _fetch_last_expense(user_id):
    conn = db_module.get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    conn.close()
    return row


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_db():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    with patch.object(db_module, "DB_PATH", db_path):
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret"

        with app.test_client() as client:
            with app.app_context():
                init_db()
            user_id = _create_test_user_and_get_id()
            yield client, user_id, db_path

    os.unlink(db_path)


# ---------------------------------------------------------------------------
# Unit tests for insert_expense
# ---------------------------------------------------------------------------

class TestInsertExpense:
    def test_insert_expense_stores_row(self, client_with_db):
        _, user_id, _ = client_with_db
        before = _count_expenses(user_id)
        insert_expense(user_id, 150.0, "Food", "2026-03-20", "Lunch")
        assert _count_expenses(user_id) == before + 1

    def test_insert_expense_stores_correct_values(self, client_with_db):
        _, user_id, _ = client_with_db
        insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")
        row = _fetch_last_expense(user_id)
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

    def test_insert_expense_with_none_description_stores_null(self, client_with_db):
        _, user_id, _ = client_with_db
        insert_expense(user_id, 50.0, "Other", "2026-03-20", None)
        row = _fetch_last_expense(user_id)
        assert row["description"] is None


# ---------------------------------------------------------------------------
# Route GET tests
# ---------------------------------------------------------------------------

class TestAddExpenseGet:
    def test_get_unauthenticated_redirects_to_login(self, client_with_db):
        client, _, _ = client_with_db
        resp = client.get("/expenses/add", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_get_authenticated_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert resp.status_code == 200

    def test_get_contains_form_with_post_method(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert b"<form" in resp.data
        assert b'method="POST"' in resp.data or b"method='POST'" in resp.data

    def test_get_contains_seven_category_options(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/expenses/add")
        assert resp.data.count(b"<option") == 7


# ---------------------------------------------------------------------------
# Route POST tests
# ---------------------------------------------------------------------------

VALID_FORM = {
    "amount": "50.0",
    "category": "Food",
    "date": "2026-03-20",
    "description": "Lunch",
}


class TestAddExpensePost:
    def test_post_unauthenticated_redirects_to_login(self, client_with_db):
        client, _, _ = client_with_db
        resp = client.post("/expenses/add", data=VALID_FORM, follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_post_valid_data_redirects_to_profile(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/add", data=VALID_FORM, follow_redirects=False)
        assert resp.status_code == 302
        assert "/profile" in resp.headers["Location"]

    def test_post_valid_data_inserts_row_in_db(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        before = _count_expenses(user_id)
        client.post("/expenses/add", data=VALID_FORM)
        assert _count_expenses(user_id) == before + 1

    def test_post_missing_amount_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/add", data={**VALID_FORM, "amount": ""})
        assert resp.status_code == 200

    def test_post_missing_amount_shows_error(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/add", data={**VALID_FORM, "amount": ""})
        assert b"Amount" in resp.data or b"error" in resp.data.lower()

    def test_post_amount_zero_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/add", data={**VALID_FORM, "amount": "0"})
        assert resp.status_code == 200

    def test_post_amount_zero_shows_error(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/add", data={**VALID_FORM, "amount": "0"})
        assert b"Amount" in resp.data or b"error" in resp.data.lower()

    def test_post_non_numeric_amount_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/add", data={**VALID_FORM, "amount": "abc"})
        assert resp.status_code == 200

    def test_post_invalid_category_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/add", data={**VALID_FORM, "category": "InvalidCat"})
        assert resp.status_code == 200

    def test_post_invalid_category_shows_error(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/add", data={**VALID_FORM, "category": "InvalidCat"})
        assert b"category" in resp.data.lower()

    def test_post_invalid_date_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/add", data={**VALID_FORM, "date": "not-a-date"})
        assert resp.status_code == 200

    def test_post_invalid_date_shows_error(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/add", data={**VALID_FORM, "date": "not-a-date"})
        assert b"Date" in resp.data or b"date" in resp.data.lower()

    def test_post_no_description_redirects_to_profile(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.post("/expenses/add", data={**VALID_FORM, "description": ""},
                           follow_redirects=False)
        assert resp.status_code == 302

    def test_post_no_description_stores_null(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        client.post("/expenses/add", data={**VALID_FORM, "description": ""})
        row = _fetch_last_expense(user_id)
        assert row["description"] is None
