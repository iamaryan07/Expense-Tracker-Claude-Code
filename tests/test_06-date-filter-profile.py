"""
Tests for Spec 06 — Date Filter for Profile Page

Covers:
- Unauthenticated redirect
- No-params (all-time) baseline
- Each preset: this-month, last-month, last-3-months, all-time
- Custom date range (valid)
- Custom date range (invalid dates → all-time fallback, no 500)
- Active preset CSS class in response
- Human-readable filter_label in response
- Empty result set renders without crash
- Stats, transactions, and categories all respect the same filter

Fixture approach:
- Patch database.db.DB_PATH to a per-test temp file so the app's
  module-level init_db() / seed_db() call never touches test data.
- Each test gets a fresh schema with only the rows it explicitly inserts,
  giving fully predictable date-range results.
"""

import os
import tempfile
import pytest
from datetime import date, timedelta
from unittest.mock import patch

import database.db as db_module
from app import app
from database.db import init_db, create_user, get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_expense(db_path, user_id, amount, category, expense_date, description="test"):
    """Insert a single expense row using parameterized query."""
    conn = db_module.get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description),
    )
    conn.commit()
    conn.close()


def _create_test_user_and_get_id(name="Test User", email="testuser@example.com",
                                  password="password123"):
    """Create a test user and return their DB id."""
    create_user(name, email, password)
    conn = db_module.get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row["id"]


def _login_session(client, user_id):
    """Inject user_id into the Flask session without going through the login form."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


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
            user_id = _create_test_user_and_get_id()
            yield client, user_id, db_path

    os.unlink(db_path)


# ---------------------------------------------------------------------------
# 1. Unauthenticated access redirects to login
# ---------------------------------------------------------------------------

class TestUnauthenticated:
    def test_profile_without_session_redirects_to_login(self, client_with_db):
        client, _uid, _dbp = client_with_db
        resp = client.get("/profile", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_profile_without_session_does_not_return_200(self, client_with_db):
        client, _uid, _dbp = client_with_db
        resp = client.get("/profile", follow_redirects=True)
        # After following the redirect we should land on the login page,
        # not the profile page.
        assert b"filter-btn" not in resp.data


# ---------------------------------------------------------------------------
# 2. No query params → all-time (HTTP 200, all-time active)
# ---------------------------------------------------------------------------

class TestNoParams:
    def test_profile_no_params_returns_200(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/profile")
        assert resp.status_code == 200

    def test_profile_no_params_shows_all_time_label(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/profile")
        assert b"All Time" in resp.data

    def test_profile_no_params_all_time_button_is_active(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/profile")
        html = resp.data.decode()
        # The All Time anchor must carry the active class
        assert "filter-btn--active" in html
        idx_active = html.index("filter-btn--active")
        # The active anchor should appear near the text "All Time"
        snippet = html[idx_active: idx_active + 200]
        assert "All Time" in snippet

    def test_profile_no_params_includes_all_expenses(self, client_with_db):
        client, user_id, _ = client_with_db
        with patch.object(db_module, "DB_PATH", client_with_db[2]):
            pass  # DB_PATH already patched by fixture
        # Insert expenses in different months
        _insert_expense(db_module.DB_PATH, user_id, 100.0, "Food", "2024-01-15")
        _insert_expense(db_module.DB_PATH, user_id, 200.0, "Bills", "2025-06-20")
        _login_session(client, user_id)
        resp = client.get("/profile")
        html = resp.data.decode()
        # Both amounts should appear somewhere in the rendered stats/transactions
        assert "₹300.00" in html or ("100" in html and "200" in html)


# ---------------------------------------------------------------------------
# Helper: fixture variant that also inserts controlled expenses
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_client(client_with_db):
    """
    Extends client_with_db with a set of controlled expenses spread across
    three calendar periods relative to 2026-05-30 (today per project context):

    - this_month  : 2026-05-10, 2026-05-20  (amounts 100, 200)
    - last_month  : 2026-04-05, 2026-04-25  (amounts 300, 400)
    - older       : 2026-02-01               (amount 500)
    - before_range: 2025-12-31               (amount 50)

    Total all-time = 100+200+300+400+500+50 = 1550
    """
    client, user_id, db_path = client_with_db

    expenses = [
        (user_id, 100.0,  "Food",        "2026-05-10", "this-month-a"),
        (user_id, 200.0,  "Transport",   "2026-05-20", "this-month-b"),
        (user_id, 300.0,  "Bills",       "2026-04-05", "last-month-a"),
        (user_id, 400.0,  "Health",      "2026-04-25", "last-month-b"),
        (user_id, 500.0,  "Shopping",    "2026-02-01", "older"),
        (user_id,  50.0,  "Other",       "2025-12-31", "before-range"),
    ]
    conn = db_module.get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()

    yield client, user_id, db_path


# ---------------------------------------------------------------------------
# 3. preset=this-month
# ---------------------------------------------------------------------------

class TestPresetThisMonth:
    def test_this_month_returns_200(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=this-month")
        assert resp.status_code == 200

    def test_this_month_active_button_marked(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=this-month")
        html = resp.data.decode()
        idx = html.index("filter-btn--active")
        snippet = html[idx: idx + 200]
        assert "This Month" in snippet

    def test_this_month_shows_only_current_month_transactions(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=this-month")
        html = resp.data.decode()
        # this-month descriptions must appear
        assert "this-month-a" in html or "this-month-b" in html
        # last-month descriptions must NOT appear in transactions
        assert "last-month-a" not in html
        assert "last-month-b" not in html

    def test_this_month_stat_total_reflects_only_current_month(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=this-month")
        html = resp.data.decode()
        # Total for this-month = 300.00 (100+200)
        assert "₹300.00" in html

    def test_this_month_filter_label_shows_month_name(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=this-month")
        html = resp.data.decode()
        # Label should contain "May 2026"
        assert "May 2026" in html

    def test_this_month_category_breakdown_reflects_filter(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=this-month")
        html = resp.data.decode()
        # Only Food and Transport categories appear in this month
        assert "Food" in html
        assert "Transport" in html
        # Bills and Health were last month — they must NOT appear in categories
        assert "Bills" not in html
        assert "Health" not in html


# ---------------------------------------------------------------------------
# 4. preset=last-month
# ---------------------------------------------------------------------------

class TestPresetLastMonth:
    def test_last_month_returns_200(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=last-month")
        assert resp.status_code == 200

    def test_last_month_active_button_marked(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=last-month")
        html = resp.data.decode()
        idx = html.index("filter-btn--active")
        snippet = html[idx: idx + 200]
        assert "Last Month" in snippet

    def test_last_month_shows_only_last_month_transactions(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=last-month")
        html = resp.data.decode()
        assert "last-month-a" in html or "last-month-b" in html
        assert "this-month-a" not in html
        assert "this-month-b" not in html

    def test_last_month_stat_total_reflects_only_last_month(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=last-month")
        html = resp.data.decode()
        # Total for last-month = 700.00 (300+400)
        assert "₹700.00" in html

    def test_last_month_filter_label_shows_april(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=last-month")
        html = resp.data.decode()
        assert "April 2026" in html


# ---------------------------------------------------------------------------
# 5. preset=last-3-months
# ---------------------------------------------------------------------------

class TestPresetLast3Months:
    def test_last_3_months_returns_200(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=last-3-months")
        assert resp.status_code == 200

    def test_last_3_months_active_button_marked(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=last-3-months")
        html = resp.data.decode()
        idx = html.index("filter-btn--active")
        snippet = html[idx: idx + 200]
        assert "Last 3 Months" in snippet

    def test_last_3_months_includes_this_and_last_month_expenses(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=last-3-months")
        html = resp.data.decode()
        # this-month and last-month rows are within 90 days
        assert "this-month-a" in html or "this-month-b" in html
        assert "last-month-a" in html or "last-month-b" in html

    def test_last_3_months_excludes_expense_older_than_90_days(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=last-3-months")
        html = resp.data.decode()
        # 2025-12-31 is more than 90 days before 2026-05-30
        assert "before-range" not in html

    def test_last_3_months_filter_label_present(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=last-3-months")
        html = resp.data.decode()
        # Label must contain a dash separator (e.g. "28 Feb – 30 May 2026")
        assert "–" in html


# ---------------------------------------------------------------------------
# 6. preset=all-time (explicit param)
# ---------------------------------------------------------------------------

class TestPresetAllTime:
    def test_all_time_explicit_returns_200(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=all-time")
        assert resp.status_code == 200

    def test_all_time_active_button_marked(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=all-time")
        html = resp.data.decode()
        idx = html.index("filter-btn--active")
        snippet = html[idx: idx + 200]
        assert "All Time" in snippet

    def test_all_time_includes_every_expense(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=all-time")
        html = resp.data.decode()
        # All-time total = 1550.00
        assert "₹1,550.00" in html

    def test_all_time_shows_all_time_label(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=all-time")
        assert b"All Time" in resp.data


# ---------------------------------------------------------------------------
# 7. preset=custom with valid dates
# ---------------------------------------------------------------------------

class TestPresetCustomValid:
    def test_custom_valid_range_returns_200(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=custom&start=2026-04-01&end=2026-04-30")
        assert resp.status_code == 200

    def test_custom_valid_range_filters_to_exact_window(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=custom&start=2026-04-01&end=2026-04-30")
        html = resp.data.decode()
        # Only April rows are in this window
        assert "last-month-a" in html or "last-month-b" in html
        assert "this-month-a" not in html
        assert "this-month-b" not in html

    def test_custom_valid_range_stat_total_matches_window(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=custom&start=2026-04-01&end=2026-04-30")
        html = resp.data.decode()
        assert "₹700.00" in html

    def test_custom_valid_range_is_inclusive_of_boundary_dates(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        # Exact boundary: only 2026-04-05
        resp = client.get("/profile?preset=custom&start=2026-04-05&end=2026-04-05")
        html = resp.data.decode()
        assert "last-month-a" in html
        assert "last-month-b" not in html

    def test_custom_valid_range_filter_label_shows_dates(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=custom&start=2026-04-01&end=2026-04-30")
        html = resp.data.decode()
        # Label should contain a formatted date range with separator
        assert "–" in html
        assert "Apr" in html

    def test_custom_preset_active_button_is_custom(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=custom&start=2026-04-01&end=2026-04-30")
        html = resp.data.decode()
        # None of the named preset buttons should be marked active
        # (custom preset has no dedicated button — just the form)
        # Verify that the four named preset buttons do NOT carry the active class
        import re
        active_anchors = re.findall(
            r'<a[^>]+filter-btn--active[^>]*>(.*?)</a>', html, re.DOTALL
        )
        named_presets = {"This Month", "Last Month", "Last 3 Months", "All Time"}
        for label in active_anchors:
            assert label.strip() not in named_presets


# ---------------------------------------------------------------------------
# 8. preset=custom with invalid dates → all-time fallback, no 500
# ---------------------------------------------------------------------------

class TestPresetCustomInvalid:
    def test_invalid_start_date_does_not_return_500(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=custom&start=not-a-date&end=also-bad")
        assert resp.status_code == 200

    def test_invalid_start_date_falls_back_to_all_time(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=custom&start=not-a-date&end=also-bad")
        assert b"All Time" in resp.data

    def test_invalid_start_date_shows_all_time_data(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=custom&start=not-a-date&end=2026-04-30")
        html = resp.data.decode()
        # Falls back to all-time → 1550.00
        assert "₹1,550.00" in html

    def test_sql_injection_in_date_param_does_not_crash(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        malicious = "'; DROP TABLE expenses; --"
        resp = client.get(
            f"/profile?preset=custom&start={malicious}&end={malicious}"
        )
        # Must not 500 — parameterized queries protect the DB
        assert resp.status_code == 200

    def test_sql_injection_falls_back_to_all_time(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        malicious = "'; DROP TABLE expenses; --"
        resp = client.get(
            f"/profile?preset=custom&start={malicious}&end={malicious}"
        )
        assert b"All Time" in resp.data

    def test_missing_end_param_with_custom_preset_does_not_crash(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=custom&start=2026-04-01")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 9. Human-readable filter label rendered on page
# ---------------------------------------------------------------------------

class TestFilterLabel:
    def test_filter_label_element_present_all_time(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile")
        assert b"filter-label" in resp.data

    def test_filter_label_contains_all_time_text(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile")
        assert b"All Time" in resp.data

    def test_filter_label_contains_month_for_this_month(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=this-month")
        assert b"May 2026" in resp.data

    def test_filter_label_contains_month_for_last_month(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=last-month")
        assert b"April 2026" in resp.data

    def test_filter_label_contains_range_for_last_3_months(self, seeded_client):
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=last-3-months")
        html = resp.data.decode()
        # Label format: "DD Mon – DD Mon YYYY"
        assert "May 2026" in html or "2026" in html
        assert "–" in html


# ---------------------------------------------------------------------------
# 10. Empty result set renders without crash
# ---------------------------------------------------------------------------

class TestEmptyResultSet:
    def test_empty_filter_returns_200(self, client_with_db):
        """Profile with a filter that matches no expenses must not crash."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        # No expenses exist in this DB — filter to a distant range
        resp = client.get("/profile?preset=custom&start=2000-01-01&end=2000-01-31")
        assert resp.status_code == 200

    def test_empty_filter_stats_show_zero_total(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/profile?preset=custom&start=2000-01-01&end=2000-01-31")
        html = resp.data.decode()
        assert "₹0.00" in html

    def test_empty_filter_transaction_count_is_zero(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/profile?preset=custom&start=2000-01-01&end=2000-01-31")
        html = resp.data.decode()
        # Transaction count stat tile must show 0
        assert ">0<" in html

    def test_empty_this_month_renders_without_crash(self, client_with_db):
        """User with zero expenses sees this-month filter without error."""
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/profile?preset=this-month")
        assert resp.status_code == 200

    def test_no_expenses_all_time_shows_zero_total(self, client_with_db):
        client, user_id, _ = client_with_db
        _login_session(client, user_id)
        resp = client.get("/profile")
        assert b"\xe2\x82\xb90.00" in resp.data  # ₹0.00 in UTF-8


# ---------------------------------------------------------------------------
# 11. All three data sections (stats, transactions, categories) obey the filter
# ---------------------------------------------------------------------------

class TestAllSectionsRespectFilter:
    def test_stats_transaction_count_matches_filtered_rows(self, seeded_client):
        """Stats transaction_count must equal the number of rows in the date window."""
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        # April has exactly 2 expenses in seeded data
        resp = client.get("/profile?preset=custom&start=2026-04-01&end=2026-04-30")
        html = resp.data.decode()
        # The Transactions stat tile should read "2"
        import re
        # Find the stat tile that follows "Transactions" label
        match = re.search(
            r'Transactions</p>\s*<p[^>]*class="stat-value[^"]*">(\d+)</p>',
            html,
            re.DOTALL,
        )
        assert match is not None, "Transactions stat tile not found"
        assert match.group(1) == "2"

    def test_categories_section_only_shows_filtered_categories(self, seeded_client):
        """Category breakdown must exclude categories with no spend in the filter window."""
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        # this-month only has Food and Transport
        resp = client.get("/profile?preset=this-month")
        html = resp.data.decode()
        # Health and Bills belong to last-month — must be absent from categories
        # (they appear only in the category-list section, not navigation)
        import re
        category_section = re.search(
            r'Spending by Category(.*?)(?=section-card|$)', html, re.DOTALL
        )
        if category_section:
            section_html = category_section.group(1)
            assert "Bills" not in section_html
            assert "Health" not in section_html

    def test_top_category_stat_reflects_filter(self, seeded_client):
        """Top Category stat must be derived from the filtered window only."""
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        # April: Health (400) > Bills (300) → top category is Health
        resp = client.get("/profile?preset=custom&start=2026-04-01&end=2026-04-30")
        html = resp.data.decode()
        import re
        match = re.search(
            r'Top Category</p>\s*<p[^>]*class="stat-value[^"]*">([^<]+)</p>',
            html,
            re.DOTALL,
        )
        assert match is not None, "Top Category stat tile not found"
        assert match.group(1).strip() == "Health"

    def test_transactions_table_only_shows_filtered_rows(self, seeded_client):
        """Recent transactions table must not show rows outside the filter window."""
        client, user_id, _ = seeded_client
        _login_session(client, user_id)
        resp = client.get("/profile?preset=custom&start=2026-05-01&end=2026-05-31")
        html = resp.data.decode()
        # last-month expense descriptions must not appear in the table
        assert "last-month-a" not in html
        assert "last-month-b" not in html
        assert "older" not in html
