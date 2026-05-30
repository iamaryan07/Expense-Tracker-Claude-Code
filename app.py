import sqlite3
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import check_password_hash
from database.db import (
    init_db, seed_db, create_user, get_user_by_email,
    get_user_by_id, get_expense_stats,
    get_recent_transactions, get_category_breakdown,
)

app = Flask(__name__)
app.secret_key = "dev-secret-key"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _resolve_date_range(preset, start_str="", end_str=""):
    today = date.today()
    if preset == "this-month":
        start = today.replace(day=1).isoformat()
        end = today.isoformat()
        label = today.strftime("%B %Y")
    elif preset == "last-month":
        last_prev = today.replace(day=1) - timedelta(days=1)
        start = last_prev.replace(day=1).isoformat()
        end = last_prev.isoformat()
        label = last_prev.strftime("%B %Y")
    elif preset == "last-3-months":
        three_months_ago = today - timedelta(days=90)
        start = three_months_ago.isoformat()
        end = today.isoformat()
        label = f"{three_months_ago.strftime('%d %b')} – {today.strftime('%d %b %Y')}"
    elif preset == "custom":
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d")
            start = start_str
            end = end_str
            label = f"{start_dt.strftime('%d %b')} – {end_dt.strftime('%d %b %Y')}"
        except ValueError:
            preset, start, end, label = "all-time", None, None, "All Time"
    else:
        preset, start, end, label = "all-time", None, None, "All Time"
    return preset, start, end, label


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required.")
            return render_template("register.html", name=name, email=email)

        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("register.html", name=name, email=email)

        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.")
            return render_template("register.html", name=name)

        flash("Account created! Please sign in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("All fields are required.")
            return render_template("login.html", email=email)

        user = get_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.")
            return render_template("login.html", email=email)

        session["user_id"] = user["id"]
        return redirect(url_for("profile"))

    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_row = get_user_by_id(session["user_id"])
    if user_row is None:
        abort(404)

    words = user_row["name"].split()
    initials = "".join(w[0].upper() for w in words[:2])
    dt = datetime.strptime(user_row["created_at"][:10], "%Y-%m-%d")
    member_since = dt.strftime("%B %Y")

    user = {
        "name": user_row["name"],
        "email": user_row["email"],
        "member_since": member_since,
        "initials": initials,
    }
    preset, start_date, end_date, filter_label = _resolve_date_range(
        request.args.get("preset", "all-time"),
        request.args.get("start", ""),
        request.args.get("end", ""),
    )

    stats        = get_expense_stats(session["user_id"], start_date, end_date)
    transactions = get_recent_transactions(session["user_id"], start_date=start_date, end_date=end_date)
    categories   = get_category_breakdown(session["user_id"], start_date, end_date)

    return render_template("profile.html", user=user, stats=stats,
                           transactions=transactions, categories=categories,
                           active_preset=preset, start_date=start_date,
                           end_date=end_date, filter_label=filter_label)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
