from flask import Flask, render_template, request, jsonify, redirect, session
import sqlite3
import os
import json
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.permanent_session_lifetime = timedelta(days=30)
DB_PATH = os.environ.get("DB_PATH", "/data/debts.db")
PASSWORD = os.environ.get("APP_PASSWORD", "1234")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(conn, table_name, column_name, column_sql):
    cols = [row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
    if column_name not in cols:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")
        conn.commit()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) if os.path.dirname(DB_PATH) else None
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            balance REAL DEFAULT 0,
            rate REAL DEFAULT 0,
            payment REAL DEFAULT 0,
            due_day INTEGER,
            paid INTEGER DEFAULT 0,
            credit_limit REAL DEFAULT 0,
            paid_this_month INTEGER DEFAULT 0,
            paycheck_group TEXT DEFAULT 'check1'
        )
        """
    )
    conn.commit()
    ensure_column(conn, "debts", "due_day", "INTEGER")
    ensure_column(conn, "debts", "paid", "INTEGER DEFAULT 0")
    ensure_column(conn, "debts", "credit_limit", "REAL DEFAULT 0")
    ensure_column(conn, "debts", "paid_this_month", "INTEGER DEFAULT 0")
    ensure_column(conn, "debts", "paycheck_group", "TEXT DEFAULT 'check1'")
    conn.close()


init_db()


def fetch_all_debts():
    conn = get_db()
    rows = conn.execute("SELECT * FROM debts ORDER BY id ASC").fetchall()
    conn.close()
    cleaned = []
    for r in rows:
        item = dict(r)
        item["paid"] = 1 if item.get("paid") else 0
        item["paid_this_month"] = 1 if item.get("paid_this_month") else 0
        item["paycheck_group"] = "check2" if item.get("paycheck_group") == "check2" else "check1"
        cleaned.append(item)
    return cleaned


@app.before_request
def make_session_permanent():
    session.permanent = True


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["logged_in"] = True
            return redirect("/dashboard")
        return render_template("login.html", error="Wrong password")

    if session.get("logged_in"):
        return redirect("/dashboard")
    return render_template("login.html", error=None)


@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect("/")
    debts = fetch_all_debts()
    return render_template("index.html", initial_debts=json.dumps(debts))


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/get_debts")
def get_debts_route():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(fetch_all_debts())


@app.route("/save", methods=["POST"])
@app.route("/save_debts", methods=["POST"])
def save_debts():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify({"error": "Invalid payload"}), 400

    conn = get_db()
    conn.execute("DELETE FROM debts")

    for d in data:
        if not isinstance(d, dict):
            continue

        due_day = d.get("due_day")
        if due_day in ("", None, "null"):
            due_day = None
        else:
            try:
                due_day = int(due_day)
                if due_day < 1 or due_day > 31:
                    due_day = None
            except Exception:
                due_day = None

        paycheck_group = str(d.get("paycheck_group", "check1") or "check1").lower()
        if paycheck_group not in ("check1", "check2"):
            paycheck_group = "check1"

        name = str(d.get("name", "")).strip()
        balance = float(d.get("balance", 0) or 0)
        rate = float(d.get("rate", 0) or 0)
        payment = float(d.get("payment", 0) or 0)
        paid = 1 if d.get("paid") else 0
        credit_limit = float(d.get("credit_limit", 0) or 0)
        paid_this_month = 1 if d.get("paid_this_month") else 0

        conn.execute(
            """
            INSERT INTO debts (
                name, balance, rate, payment, due_day, paid, credit_limit, paid_this_month, paycheck_group
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, balance, rate, payment, due_day, paid, credit_limit, paid_this_month, paycheck_group),
        )

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
