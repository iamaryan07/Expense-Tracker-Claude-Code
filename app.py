import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from database.db import init_db, seed_db, create_user, get_user_by_email

app = Flask(__name__)
app.secret_key = "dev-secret-key"

with app.app_context():
    init_db()
    seed_db()


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

    user = {
        "name": "Aryan Balhara",
        "email": "aryan@example.com",
        "member_since": "January 2025",
        "initials": "AB",
    }
    stats = {
        "total_spent": "₹5,599.00",
        "transaction_count": 8,
        "top_category": "Shopping",
    }
    transactions = [
        {"date": "2025-05-20", "description": "Birthday gift",       "category": "Other",         "amount": "₹500.00"},
        {"date": "2025-05-17", "description": "Coffee and snacks",   "category": "Food",          "amount": "₹80.00"},
        {"date": "2025-05-14", "description": "New headphones",      "category": "Shopping",      "amount": "₹2,300.00"},
        {"date": "2025-05-10", "description": "Netflix subscription", "category": "Entertainment", "amount": "₹599.00"},
        {"date": "2025-05-08", "description": "Pharmacy — vitamins", "category": "Health",        "amount": "₹350.00"},
    ]
    categories = [
        {"name": "Shopping",      "amount": "₹2,300.00", "pct": 41},
        {"name": "Bills",         "amount": "₹1,200.00", "pct": 21},
        {"name": "Entertainment", "amount": "₹599.00",   "pct": 11},
        {"name": "Food",          "amount": "₹530.00",   "pct": 10},
        {"name": "Other",         "amount": "₹500.00",   "pct": 9},
        {"name": "Health",        "amount": "₹350.00",   "pct": 6},
        {"name": "Transport",     "amount": "₹120.00",   "pct": 2},
    ]
    return render_template("profile.html", user=user, stats=stats,
                           transactions=transactions, categories=categories)


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
